"""Line manners that only show up on a real phone line: a caller who pauses mid-sentence, and a model
that now and then writes its whole reply twice — or writes a tool call out as text instead of making it.
"""

import asyncio
import re
import time
import uuid

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    LLMContextFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.deepgram.tts import DeepgramTTSService, DeepgramTTSSettings
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService, ElevenLabsTTSSettings
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.llm_service import FunctionCallFromLLM
from pipecat.turns.user_mute.function_call_user_mute_strategy import FunctionCallUserMuteStrategy
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import SpeechTimeoutUserTurnStopStrategy

from . import config, languages, tools
from .session import CallSession


def looks_unfinished(text: str) -> bool:
    """Deepgram closes a finished utterance with . ? or ! — of the first 240 caller turns heard on the
    harness, the 21 that ended without one were all half-sentences ("Yeah. So", "I need a", a DNI in pieces)."""
    text = text.strip()
    return bool(text) and text[-1] not in ".?!"


class PatientTurnStop(SpeechTimeoutUserTurnStopStrategy):
    """Ends the caller's turn after a short silence, unless what they said so far is a half-sentence:
    that gets `unfinished_extra_secs` more. Replying into such a pause loses the sentence, because the
    harness's caller stops talking the moment it hears us."""

    def __init__(self, *, unfinished_extra_secs: float, **kwargs):
        super().__init__(**kwargs)
        self._extra = unfinished_extra_secs
        self._grace_task: asyncio.Task | None = None
        self._grace_given = False

    async def _discard_pending_end_of_turn(self):
        self._grace_given = False
        await super()._discard_pending_end_of_turn()

    async def _cancel_all_tasks(self):
        await super()._cancel_all_tasks()
        if self._grace_task:
            await self.task_manager.cancel_task(self._grace_task)
            self._grace_task = None

    async def _maybe_trigger_user_turn_stopped(self):
        if self._grace_task:
            return  # still giving the caller time to finish
        ready = not self._vad_user_speaking and self._text and self._user_speech_wait_done and self._stt_wait_done
        if ready and not self._grace_given and looks_unfinished(self._text):
            self._grace_given = True
            self._grace_task = self.task_manager.create_task(self._grace(), f"{self}::_grace")
            return
        await super()._maybe_trigger_user_turn_stopped()

    async def _grace(self):
        try:
            await asyncio.sleep(self._extra)
        except asyncio.CancelledError:
            return
        finally:
            self._grace_task = None  # cleared before triggering: the turn's reset must not cancel this very task
        await super()._maybe_trigger_user_turn_stopped()


class ReplayFilter:
    """Drops a reply the model writes a second time in the same response.

    Seen live: "Good morning. How can I help you today?Good morning. How can I help you today?" — 20 completion
    tokens for a 10-token sentence. Spoken, it doubles the call's length, and once one doubled reply is in the
    context the model copies the pattern for the rest of the call. The replay can start anywhere, even in the
    middle of a streamed chunk, so this works on characters: whatever follows a point where the text starts
    over is held back while it keeps matching the beginning, and released unchanged if the match breaks.
    """

    MIN_CHARS = 12  # a reply this short starting again ("Yes. Yes, of course") is not a replay

    def __init__(self):
        self.full = ""
        self._sent = 0

    def feed(self, text: str) -> str:
        self.full += text
        upto = self._replay_start()
        if upto is None:
            upto = len(self.full)
        out = self.full[self._sent:upto] if upto > self._sent else ""
        self._sent = max(self._sent, upto)
        return out

    def _replay_start(self) -> int | None:
        head = self.full.lstrip()
        shift = len(self.full) - len(head)
        for k in range(self.MIN_CHARS, len(head)):
            tail = head[k:].lstrip()
            if tail and head[:k].startswith(tail):
                return k + shift
        return None


_SENTENCE_END = re.compile(r"[.?!…][\"')\]]?\s")
# Nothing a receptionist says has braces, code fences or "default_api" in it.
_NOT_SPEECH = re.compile(r"default_api|```|[{}]|\[\]|\bcat\s*=|\bcall\s*:")
_CORRECTION = ("[SYSTEM] Your last reply was a tool call written out as text. Nothing ran and the caller heard nothing. "
               "Make that call now through function calling, or answer the caller in plain words.")


class GuardedGoogleLLM(GoogleLLMService):
    """Gemini through Pipecat, with two of its habits taken out before they reach the voice.

    Replayed replies are dropped (ReplayFilter). Text is released one whole sentence at a time — the voice
    cannot start earlier anyway — and a sentence that is not speech is never spoken: it is a tool call the
    model wrote as text ("cat=default_api:find_patient{name:…}"). Seen live, twice in one scored run: the
    gibberish was read out to the caller, no lookup ever ran, the model copied itself turn after turn, and
    both calls died at the three-minute wall. The written call is parsed and run as the real call it should
    have been; if it cannot be parsed, the model is told once and asked again. Either way the text stays
    out of the context, so there is nothing for the model to copy.
    """

    MAX_CORRECTIONS = 2

    _replay: ReplayFilter | None = None
    _pending = ""
    _leaked = ""
    _context = None
    _corrections = 0

    async def _process_context(self, context):
        self._replay, self._pending, self._leaked, self._context = ReplayFilter(), "", "", context
        await super()._process_context(context)

    async def _push_llm_text(self, text: str):
        kept = self._replay.feed(text) if self._replay else text
        if self._leaked:
            self._leaked += kept
            return
        self._pending += kept
        while (m := _SENTENCE_END.search(self._pending)) and not self._leaked:
            sentence, self._pending = self._pending[:m.end()], self._pending[m.end():]
            await self._say_or_catch(sentence)

    async def _say_or_catch(self, text: str):
        if _NOT_SPEECH.search(text):
            self._leaked, self._pending = text + self._pending, ""
        elif text.strip():
            await super()._push_llm_text(text)

    async def run_function_calls(self, function_calls):
        # Called once per response, after the last streamed chunk and before the response is closed.
        if self._pending and not self._leaked:
            await self._say_or_catch(self._pending)
        self._pending = ""
        if self._leaked and not function_calls:
            written = tools.parse_leaked_calls(self._leaked)
            logger.warning(f"{self}: tool call written as text, recovered {[n for n, _ in written]}: {self._leaked[:200]!r}")
            function_calls = [FunctionCallFromLLM(context=self._context, tool_call_id=str(uuid.uuid4()),
                                                  function_name=name, arguments=args) for name, args in written]
            if not function_calls and self._corrections < self.MAX_CORRECTIONS:
                self._corrections += 1
                self._context.add_message({"role": "user", "content": _CORRECTION})
                await self.queue_frame(LLMContextFrame(context=self._context))
        if function_calls:
            self._corrections = 0
        await super().run_function_calls(function_calls)


def speaks_with_elevenlabs(voice: str = "") -> bool:
    """A call may name its voice (pipelines.py); one that does not gets ElevenLabs whenever its key is there."""
    return (voice or ("elevenlabs" if config.ELEVENLABS_API_KEY else "deepgram")) == "elevenlabs"


def voice_service(language: str, voice: str = "") -> ElevenLabsTTSService | DeepgramTTSService:
    """The agent's voice. ElevenLabs' one voice reads English and Spanish alike and hears the language from the text.
    It is not told the language: that is part of its connection, and at a change of language ElevenLabs took two
    seconds to close the old one — measured on a Spanish call, right before the first Spanish sentence."""
    if speaks_with_elevenlabs(voice):
        return ElevenLabsTTSService(api_key=config.ELEVENLABS_API_KEY, settings=ElevenLabsTTSSettings(
            voice=config.ELEVENLABS_VOICE_ID, model=config.ELEVENLABS_MODEL))
    return DeepgramTTSService(api_key=config.DEEPGRAM_API_KEY, settings=DeepgramTTSSettings(voice=languages.VOICES[language]))


class VoiceRouter(FrameProcessor):
    """Sits between the model and the voice and keeps track of the language the agent is speaking — the stock
    phrases follow it. Deepgram has a voice per language, so there each sentence is spoken by the voice of the
    language it is written in: the voice changes with a settings update sent just ahead of the sentence, and the
    two can never be out of step."""

    def __init__(self, session: CallSession):
        super().__init__()
        self._session = session

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMTextFrame):
            language = languages.reply_language(frame.text, self._session.language)
            if language != self._session.language:
                self._session.language = language
                self._session.log("voice", language=language)
                if not speaks_with_elevenlabs(self._session.voice):
                    await self.push_frame(TTSUpdateSettingsFrame(delta=DeepgramTTSSettings(voice=languages.VOICES[language])))
        await self.push_frame(frame, direction)


class LookupMute(FunctionCallUserMuteStrategy):
    """The caller is not listened to from the moment a lookup starts until a second into the agent's answer.

    "One moment, please." draws an "Okay" or "Sure, I'll wait" from most people. Measured on 340 holding
    phrases: 78 acknowledgements, of which 38 cut the agent's reply off, 22 threw the model's run away and 18
    cancelled the lookup itself — six seconds lost each, and in 23 calls a decision recorded on an offer the
    caller had not heard. Pipecat's own strategy stops listening while the lookup runs; this one also covers
    the answer's first second, which is where the late "Okay" lands. It can never stay deaf: SAFETY_SECS after
    the last lookup returned it listens again whatever happened.
    """

    REPLY_TAIL_SECS = 1.0
    SAFETY_SECS = 6.0

    def __init__(self):
        super().__init__()
        self._bot_speaking = False
        self._listen_again_at = 0.0  # while a reply to a lookup is owed or in its first second

    async def process_frame(self, frame: Frame) -> bool:
        looking_up = await super().process_frame(frame)
        now = time.monotonic()
        began_to_speak = isinstance(frame, BotStartedSpeakingFrame) and not self._bot_speaking
        if isinstance(frame, (BotStartedSpeakingFrame, BotStoppedSpeakingFrame)):
            self._bot_speaking = isinstance(frame, BotStartedSpeakingFrame)
        if looking_up:
            self._listen_again_at = now + self.SAFETY_SECS  # re-armed until the last lookup has returned
        elif began_to_speak and now < self._listen_again_at:
            self._listen_again_at = now + self.REPLY_TAIL_SECS  # the answer has begun
        return looking_up or now < self._listen_again_at


class SpokenClock(FrameProcessor):
    """Sits after the phone line's output and counts the seconds of the current reply that were really played.

    Pipecat puts a sentence into the model's context when it is synthesised, not when it is heard. Seen live, in
    22 calls: an offer went to the voice, the caller's "Ajá" cut it off a third of a second later, the context
    still held the whole offer with "Would you like me to book that?" — and the model booked on the "Ajá".
    """

    CHARS_PER_SEC = 16.0  # both voices, measured over the logged calls
    HEARD_SHARE = 0.8

    def __init__(self):
        super().__init__()
        self._played = 0.0
        self._since: float | None = None

    def heard(self, reply: str) -> bool:
        """Whether the caller can have heard this reply, given how long the voice has been playing it."""
        played = self._played + (time.monotonic() - self._since if self._since is not None else 0.0)
        return played >= self.HEARD_SHARE * len(reply) / self.CHARS_PER_SEC

    def note(self, frame: Frame) -> None:
        now = time.monotonic()
        if isinstance(frame, LLMFullResponseStartFrame):  # a new reply: the holding phrase before it does not count
            self._played, self._since = 0.0, (now if self._since is not None else None)
        elif isinstance(frame, BotStartedSpeakingFrame) and self._since is None:
            self._since = now
        elif isinstance(frame, BotStoppedSpeakingFrame) and self._since is not None:
            self._played, self._since = self._played + now - self._since, None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        self.note(frame)
        await self.push_frame(frame, direction)
