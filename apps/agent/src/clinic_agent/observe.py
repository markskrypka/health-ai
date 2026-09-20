"""What the screens see of a call while it runs — watched from beside the pipeline, never from inside it.

Pipecat hands every frame that moves between two processors to its observers through a queue of their own, so
nothing here can slow a call down or break one: an observer that fails is an observer that stops reporting.

Four things reach the call's log from here: the caller's words as they are recognised (`hearing`), the agent's
words as they are spoken (`speaking`), the seconds between the caller's last word and the agent's first
(`latency`), and at the end what the call used (`usage`) — tokens, characters, seconds: what it cost.
"""

import time
from collections import deque

from loguru import logger
from pipecat.frames.frames import InterimTranscriptionFrame, MetricsFrame, TranscriptionFrame, TTSTextFrame
from pipecat.metrics.metrics import LLMUsageMetricsData, TTSUsageMetricsData
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.processors.frame_processor import FrameProcessor

from .session import CallSession

HEARING_EVERY_SECS = 0.12  # interim results arrive faster than a screen needs them


class CallObserver(BaseObserver):
    def __init__(self, session: CallSession, spoken_after: FrameProcessor):
        """`spoken_after` is the line's output: a word leaves it at the moment its audio does, so that hop — and no
        earlier one, where a whole sentence arrives at once from the voice — is when the word is reported."""
        super().__init__()
        self._session = session
        self._spoken_after = spoken_after
        self._seen: deque[int] = deque(maxlen=512)  # a frame passes here once per hop; it is reported once
        self._settled: list[str] = []  # the parts of the caller's turn the recogniser has finished with
        self._last_heard, self._heard_at = "", 0.0
        self.usage = {"llm_prompt_tokens": 0, "llm_completion_tokens": 0, "llm_cached_tokens": 0, "tts_characters": 0}

    def turn_ended(self) -> None:
        """The caller's turn is in the log whole: the next words start a new one."""
        self._settled, self._last_heard = [], ""

    async def on_push_frame(self, data: FramePushed) -> None:
        frame = data.frame
        if not isinstance(frame, (InterimTranscriptionFrame, TranscriptionFrame, TTSTextFrame, MetricsFrame)):
            return
        if isinstance(frame, TTSTextFrame) and data.source is not self._spoken_after:
            return
        if frame.id in self._seen:
            return
        self._seen.append(frame.id)
        try:
            if isinstance(frame, InterimTranscriptionFrame):
                self._hear(frame.text, settled=False)
            elif isinstance(frame, TranscriptionFrame):
                self._hear(frame.text, settled=True)
            elif isinstance(frame, TTSTextFrame):
                if frame.text.strip():
                    self._session.log("speaking", text=frame.text.strip())
            else:
                for item in frame.data:
                    if isinstance(item, LLMUsageMetricsData):
                        self.usage["llm_prompt_tokens"] += item.value.prompt_tokens or 0
                        self.usage["llm_completion_tokens"] += item.value.completion_tokens or 0
                        self.usage["llm_cached_tokens"] += item.value.cache_read_input_tokens or 0
                    elif isinstance(item, TTSUsageMetricsData):
                        self.usage["tts_characters"] += item.value or 0
        except Exception:  # a screen going without its live words is never worth a call
            logger.exception(f"[{self._session.call_id}] observer")

    def _hear(self, text: str, settled: bool) -> None:
        text = text.strip()
        if not text:
            return
        if settled:
            self._settled.append(text)
        so_far = " ".join(self._settled if settled else [*self._settled, text])
        now = time.monotonic()
        if so_far != self._last_heard and (settled or now - self._heard_at >= HEARING_EVERY_SECS):
            self._last_heard, self._heard_at = so_far, now
            self._session.log("hearing", text=so_far)


def latency_observer(session: CallSession) -> UserBotLatencyObserver:
    """Pipecat's own measure of the pause a caller sits through, written to the call's log turn by turn."""
    observer = UserBotLatencyObserver()

    @observer.event_handler("on_latency_measured")
    async def on_latency(_observer, seconds: float):
        session.log("latency", secs=round(seconds, 2))

    return observer
