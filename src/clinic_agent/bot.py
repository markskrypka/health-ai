"""One call = one pipeline. Everything here is built fresh per socket; nothing is shared across calls
except the stateless clinic API client and the static catalogue.

Deepgram hears (Nova-3), Gemini Flash decides through the tools in tools.py, and ElevenLabs speaks
(Deepgram Aura-2 when no ElevenLabs key is set — see speech.voice_service).
Audio stays at the phone line's 8 kHz end to end, so nothing is resampled.
"""

import asyncio

from fastapi import WebSocket
from loguru import logger
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import LLMMessagesAppendFrame, STTUpdateSettingsFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import WorkerRunner
from pipecat.pipeline.task import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair, LLMUserAggregatorParams
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService, DeepgramSTTSettings
from pipecat.services.google.llm import GoogleLLMSettings, GoogleThinkingConfig
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams, FastAPIWebsocketTransport
from pipecat.turns.user_turn_strategies import UserTurnStrategies

from . import config, languages, prompt, tools
from .clinic import ClinicClient
from .session import CallSession
from .speech import GuardedGoogleLLM, LookupMute, PatientTurnStop, SpokenClock, VoiceRouter, voice_service

GREETING = "Clínica Arenal, good morning. How can I help you?"
LINE_RATE = 8000  # Twilio Media Streams: 8 kHz µ-law
# One published caller goes silent for eight seconds on purpose, and the harness's caller loses its sentence
# whenever we talk over it: a nudge at seven seconds landed exactly on callers who were about to speak.
QUIET_LINE_SECS = 10.0
_WRAP_UP = ("[CLOCK] This call will be cut off in about a minute. Stop asking and stop confirming. "
            "Call the tool that records the outcome NOW with the best information you have — register_patient, book, "
            "reschedule, cancel or end_without_booking — then say goodbye in one short sentence.")
_WRAP_UP_WITH_OFFER = ("[CLOCK] This call will be cut off in about a minute. Do NOT search again and do not ask "
                       "anything else. Your last offer, slot_ref {ref}, is what the caller is answering: unless they "
                       "refused it, record it NOW with book — or with reschedule if they asked to move an appointment — "
                       "then say goodbye in one short sentence.")
_NOT_HEARD = ("[LINE] The caller spoke over you: they did not hear your last reply, so whatever they say next is not "
              "an answer to it. Say it again in one short sentence, then wait for their answer.")
# A turn ends after this much silence (plus the VAD's 0.2 s). Pipecat's default end-of-turn model
# closes the turn at "Hi." and after each group of a dictated id; a plain timeout keeps an id whole,
# and behaves the same in every language.
TURN_END_SILENCE_SECS = 0.9
# …unless the caller stopped mid-sentence ("Yeah. So", "I need a"): then they get this much longer to go on.
UNFINISHED_EXTRA_SECS = 2.0

# Names a generic model mishears: doctors, sites, insurers.
_KEYTERMS = ["Clínica Arenal", "Arenal Centro", "Arenal Norte", "Arenal Sur", "DNI", "NIE",
             "Sanitas", "Adeslas", "DKV", "ASISA", "Mapfre", "Caser", "Cigna", "AXA", "Nueva Mutua"]


def _tool_handler(name: str, session: CallSession, api: ClinicClient):
    fn = tools.TOOLS[name][0]

    async def handler(params: FunctionCallParams) -> None:
        args = dict(params.arguments or {})
        session.log("tool_call", name=name, args=args)
        try:
            result = await fn(session, api, **args)
        except TypeError as err:  # the model passed an argument the tool does not take
            result = {"status": "error", "say": f"Bad arguments for {name}: {err}"}
        except Exception as err:  # never let a tool crash the call
            logger.exception(f"[{session.call_id}] tool {name} failed")
            result = {"status": "error", "say": f"{name} failed ({type(err).__name__}). Apologise briefly and try once more."}
        session.log("tool_result", name=name, result=result)
        await params.result_callback(result)

    return handler


async def run_call(websocket: WebSocket, call_data: dict, api: ClinicClient, active: dict[str, CallSession]) -> None:
    body = call_data.get("body") or {}
    session = CallSession(call_id=call_data["call_id"], from_number=body.get("from_number") or None,
                          dry_run=config.DRY_RUN_SUBMIT)
    active[session.call_id] = session
    session.log("call_started", has_caller_id=bool(session.from_number))
    catalogue = await api.catalogue()

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"], call_sid=session.call_id,
        params=TwilioFrameSerializer.InputParams(auto_hang_up=False))  # no Twilio account behind this wire
    transport = FastAPIWebsocketTransport(websocket, FastAPIWebsocketParams(
        audio_in_enabled=True, audio_out_enabled=True, add_wav_header=False, serializer=serializer))

    stt = DeepgramSTTService(api_key=config.DEEPGRAM_API_KEY, settings=DeepgramSTTSettings(
        model="nova-3", language="multi", smart_format=True,
        keyterm=_KEYTERMS + [p["name"].split()[-1] for p in catalogue["providers"]]))
    llm = GuardedGoogleLLM(api_key=config.GOOGLE_API_KEY, settings=GoogleLLMSettings(
        model=config.LLM_MODEL,
        system_instruction=prompt.build(catalogue, session.now, bool(session.from_number)),
        thinking=GoogleThinkingConfig(thinking_level="minimal")))
    tts = voice_service(session.language)

    schemas = [FunctionSchema(name=n, description=desc, properties=props, required=req)
               for n, (_, desc, props, req) in tools.TOOLS.items()]
    for name in tools.TOOLS:
        llm.register_function(name, _tool_handler(name, session, api))

    # The greeting is spoken by code, so the model has to be told it already happened.
    context = LLMContext(messages=[{"role": "assistant", "content": GREETING}], tools=ToolsSchema(standard_tools=schemas))
    user_agg, assistant_agg = LLMContextAggregatorPair(context, user_params=LLMUserAggregatorParams(
        vad_analyzer=SileroVADAnalyzer(), user_idle_timeout=QUIET_LINE_SECS, user_mute_strategies=[LookupMute()],
        user_turn_strategies=UserTurnStrategies(
            stop=[PatientTurnStop(user_speech_timeout=TURN_END_SILENCE_SECS,
                                  unfinished_extra_secs=UNFINISHED_EXTRA_SECS)])))

    spoken = SpokenClock()
    pipeline = Pipeline([transport.input(), stt, user_agg, llm, VoiceRouter(session), tts, transport.output(), spoken, assistant_agg])
    worker = PipelineWorker(pipeline, enable_rtvi=False, params=PipelineParams(
        audio_in_sample_rate=LINE_RATE, audio_out_sample_rate=LINE_RATE, enable_metrics=True, enable_usage_metrics=True))

    @transport.event_handler("on_client_connected")
    async def on_connected(_transport, _client):
        # Already in the context above; appended again it sat there twice, and a model that reads a doubled
        # first line starts doubling its own.
        await worker.queue_frames([TTSSpeakFrame(GREETING, append_to_context=False)])

    @transport.event_handler("on_client_disconnected")
    async def on_disconnected(_transport, _client):
        await worker.cancel(reason="caller hung up")

    holding = {"said": False}

    @llm.event_handler("on_function_calls_started")
    async def on_lookup_started(_service, function_calls):
        # Two lookups in a row mean ~6 s of model rounds. The harness cuts a line that goes quiet,
        # so say one short holding phrase per caller turn — never before a submission's confirmation.
        names = {getattr(fc, "function_name", "") for fc in function_calls}
        if not holding["said"] and names & {"find_patient", "find_slots", "list_appointments", "nearest_site"}:
            holding["said"] = True
            # Kept out of the context: a model that reads its own holding phrases starts writing them too.
            await worker.queue_frames([TTSSpeakFrame(languages.HOLDING[session.language], append_to_context=False)])

    @user_agg.event_handler("on_user_turn_stopped")
    async def on_user_said(_agg, _strategy, message):
        holding["said"] = False
        session.search_locked = False  # the caller spoke after the clock: what they ask for now is theirs to get
        text = getattr(message, "content", str(message))
        session.heard.append(text)
        session.log("caller", text=text)
        if not session.catalan and languages.sounds_catalan(session.heard):
            # Deepgram's multilingual model has no Catalan and mangles its dates; the Catalan model (Nova-2,
            # which takes no keyterms) hears it word for word. The service reconnects with the new settings.
            session.catalan = True
            session.log("listening_model", language="ca")
            await worker.queue_frames([STTUpdateSettingsFrame(delta=DeepgramSTTSettings(model="nova-2", language="ca", keyterm=None))])

    @assistant_agg.event_handler("on_assistant_turn_stopped")
    async def on_agent_said(_agg, message):
        text = getattr(message, "content", str(message))
        session.said.append(text)
        # The context already holds the whole reply, played or not. A reply the caller talked over is marked as
        # unheard for the model, and code refuses one decision on it (tools._not_heard).
        cut_off = bool(text) and getattr(message, "interrupted", False) and not spoken.heard(text)
        if text:  # a turn that was only a tool call says nothing either way
            session.unheard = text if cut_off else None
        session.log("agent", text=text, **({"cut_off": True} if cut_off else {}))
        if cut_off:
            context.add_message({"role": "user", "content": _NOT_HEARD})

    @user_agg.event_handler("on_user_turn_idle")
    async def on_quiet_line(_agg):
        # Silence from our side gets the call cut off; a quiet caller gets one nudge at a time.
        # Once the outcome is submitted the call is over: the caller is just hanging up.
        session.log("quiet_line")
        if not session.submissions:
            await worker.queue_frames([TTSSpeakFrame(languages.NUDGE[session.language])])

    async def wrap_up_clock() -> None:
        await asyncio.sleep(config.WRAP_UP_AT_SECS)
        if not session.submissions:  # a wrong-ish record can pass; an empty one cannot
            offer = session.last_offered_slot
            session.search_locked = bool(offer)
            session.log("wrap_up_clock", offer=offer)
            text = _WRAP_UP_WITH_OFFER.format(ref=offer) if offer else _WRAP_UP
            await worker.queue_frames([LLMMessagesAppendFrame(messages=[{"role": "user", "content": text}], run_llm=True)])

    clock = asyncio.create_task(wrap_up_clock())
    try:
        await WorkerRunner(handle_sigint=False).run(worker)
    finally:
        clock.cancel()
        # Decisions are POSTed now: the window stays open 30 s after the socket closes. Shielded, because
        # the pipeline's own cancellation must not interrupt the one thing the leaderboard reads.
        await asyncio.shield(tools.finalize(session, api))
        session.log("call_ended", submissions=session.submissions, posted=session.posted)
        active.pop(session.call_id, None)
        logger.info(f"[{session.call_id}] ended with {session.submissions} → {session.posted}")
