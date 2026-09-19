# Voice orchestration layer — frameworks and platforms (research probe)

Date: 2026-09-18 · Timebox ~20 min · Legend: **[V]** verified on a primary source today · **[S]** strong (several credible secondary sources, or a search snippet of a primary doc not opened) · **[I]** inferred.
Team constraints folded in (coordinator update): TypeScript/Node-first · Google AI/Cloud credits (largest) + an OpenAI key, Gemini preferred · we OWN the orchestration (managed platforms = benchmark only) · harness contract still unknown (not registered yet).

## Question
Which voice-agent orchestration layer do we build on, given a TS team, Google credits, literal scoring, ten simultaneous calls, five languages and a bad line?

## Decision it informs
The core runtime of the product, and where the line sits between "our code" (dialog state, tool gating, the what-we-did report, observability) and "rented plumbing" (audio transport, turn-taking, model I/O).

## Findings

### A. TypeScript-viable options (ranked)
1. **Custom Node edge + Gemini Live via `@google/genai`** — no framework; a `ws` server, a transport adapter, a tool dispatcher.
   - [V] Live API models today: Gemini 3.8 Live (default), 3.8 Live Extended Thinking, 3.1 Flash Live Preview (legacy). Input raw PCM16, "will resample if needed so any sample rate can be sent" (so send `audio/pcm;rate=8000` straight from the phone leg); output 24 kHz. No mu-law support — transcode yourself. 99 languages **including Catalan, Galician, Basque**; native-audio models switch language automatically, no `language_code` (restrict via system instruction). Server-side VAD is configurable (`silenceDurationMs`, sensitivities); barge-in arrives as an `interrupted` server message and the client must flush playback. Audio session cap 15 min; async `NON_BLOCKING` function calls on 3.8 Live. https://ai.google.dev/gemini-api/docs/live-api/capabilities
   - [V] Concurrency on an AI Studio key is NOT guaranteed: Google staff — "we currently do not guarantee support for concurrent sessions… limitations are on the Tokens per minute basis". https://discuss.ai.google.dev/t/official-concurrent-session-rps-limits-for-gemini-live-api-where-are-they-documented/174664 · [S] Vertex AI PayGo: up to 1,000 concurrent Live sessions per project → **use Vertex with the Cloud credits for the ten-at-once case**. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/live-api/start-manage-session
   - [S] Counter-evidence: output audio freezing mid-call with the socket still open (google-gemini/cookbook #1225, #1197); VAD self-interrupting the greeting on "Hello?"; spoken "tool_outputs" artefacts (python-genai #789); naive chunk-wise resampling sounds choppy. https://github.com/google-gemini/cookbook/issues/1225 · https://github.com/google-gemini/cookbook/issues/1197 · https://github.com/googleapis/python-genai/issues/789 · https://discuss.ai.google.dev/t/live-api-support-for-mulaw-g711-ulaw-input-output/86053
   - [S] Reference Node/TS bridges exist (Twilio Media Streams ↔ Gemini Live, barge-in, mark-confirmed playback) but are tiny projects — read, do not depend: https://github.com/yakovsinwani/realtime-voice-agents ([V] 3 stars, created 2026-08) · https://github.com/rohitcoding1991/twilio-gemini-caller · https://dev.to/googleai/add-telephony-to-a-gemini-live-agent-with-twilio-1elc
   - [I] Only TS option that fits every possible harness contract (WS, HTTP, phone via media streams). Cost: we own transcoding, playback flushing, silence watchdog + session resumption.
2. **LiveKit Agents JS** — the only full-featured, actively maintained TS voice framework.
   - [V] `@livekit/agents` 1.9.0 (2026-09-15), Apache-2.0, weekly releases; 930 stars / 366 open issues+PRs (Python repo: 14.3k stars, 822 open, 1.8.2 on 2026-09-15). 38 Node plugins incl. google, openai, azure, soniox, deepgram, elevenlabs, cartesia, krisp, silero, livekit (turn detector). Node google plugin = Gemini LLM + `realtime/` (Gemini Live) + beta Gemini STT/TTS; **no Google Cloud Speech (Chirp) STT class in Node**. https://github.com/livekit/agents-js · https://api.github.com/repos/livekit/agents-js/contents/plugins
   - [S] Gemini Live plugin tracks new models (3.8 Live) and mid-session updates; PR text calls the Python change "authoritative" and ports are made by a bot → Node follows Python, slightly behind. https://github.com/livekit/agents-js/pull/2503 · https://docs.livekit.io/agents/models/realtime/plugins/gemini/
   - [V] **Needs a LiveKit server**; the agent is a room participant, so it is reachable only via WebRTC or SIP — no raw WebSocket/HTTP ingress. Inbound phone: LiveKit Phone Numbers (US numbers only on the pricing page) or a SIP trunk (Twilio, Telnyx, Plivo, Exotel, Wavix, Sinch, didlogic); Krisp noise cancellation is a flag on the inbound trunk. https://docs.livekit.io/agents/start/telephony/
   - [V] LiveKit Cloud Build (free): **5 concurrent agent sessions** for cloud-deployed agents, 5 STT + 5 TTS LiveKit-Inference connections, 100 participants, 1,000 agent minutes; Ship $50/mo → 20 sessions. Quotas page also meters adaptive interruption (40k req/mo) and hosted turn detection (7.5k req/mo) on Build. [I] A self-hosted worker with our own Google/OpenAI keys avoids the 5-session and inference caps (10 calls = 20 participants). https://livekit.com/pricing · https://docs.livekit.io/deploy/admin/quotas-and-limits/
   - [S] Built-in tests are text-mode only (Vitest in Node): no audio, noise or telephony coverage. https://docs.livekit.io/agents/start/testing/test-framework/ · [V] Python 1.8.0 moved telemetry to OpenTelemetry GenAI conventions (Langfuse/Datadog); Node parity not checked. https://github.com/livekit/agents/releases
3. **OpenAI Agents SDK (TS) realtime** — [V] v0.18.0 (2026-09-10), MIT. Transports: `OpenAIRealtimeWebSocket`, `OpenAIRealtimeWebRTC`, `OpenAIRealtimeSIP`, plus Twilio and Cloudflare extensions; custom transports via `RealtimeTransportLayer`; **OpenAI realtime models only** (no Gemini → spends the OpenAI key, not Google credits). https://openai.github.io/openai-agents-js/guides/voice-agents/transport/ · https://openai.github.io/openai-agents-js/extensions/twilio/ · [S] SIP is native: point a trunk at OpenAI, no media server. https://www.twilio.com/en-us/blog/developers/tutorials/product/openai-realtime-api-elastic-sip-trunking · Not found: realtime concurrent-session limit for low usage tiers; Galician/Basque speech quality.
4. **jambonz (Node SDK `@jambonz/node-client-ws`)** — [V] MIT, feature-server pushed 2026-09-15. `llm` verb bridges a SIP call to OpenAI Realtime, GPT Live, Deepgram VA, Ultravox, ElevenLabs, **Gemini Live**, AssemblyAI, xAI; tool calls reach our Node app via `toolHook`, events via `eventHook` (wildcard filter); it handles barge-in flush. https://docs.jambonz.org/verbs/verbs/llm · [I] Telephony-only (SIP/PSTN): worthless if the harness is WS/HTTP; self-hosting is a weekend risk. Not found: hosted jambonz.cloud trial terms.
5. **Cloudflare Agents voice (`withVoice`)** — [V] Beta. WebSocket PCM, STT → our `onTurn()` → sentence-chunked TTS, Durable Object per call with SQLite history; Twilio/Plivo adapters (8 kHz mu-law), Telnyx; providers: Workers AI Flux/Nova-3 STT, Workers AI TTS, Deepgram, ElevenLabs; energy-threshold interruption. No Gemini Live path; no listed STT for Galician/Basque. README: API "will break between releases". https://developers.cloudflare.com/agents/api-reference/voice/ · https://github.com/cloudflare/agents/blob/main/packages/voice/README.md · [I] Cloudflare sponsors the event: good home for the live dashboard, risky as the voice core.
6. **Mastra voice** — [V] a provider abstraction, not an orchestrator (no telephony, turn-taking or barge-in layer); its Gemini Live provider has fresh open bugs: usage never emitted (#23719), API-key sessions pinned to `v1alpha` (#23720), PCM frames without sample rate (#23722). https://github.com/mastra-ai/mastra/issues/23720
7. **Layercode** — dead for us. [V] `layercode.com/pricing` 301-redirects to toyo.ai (an "AI executive assistant"). [S] Team "fully pivoted" after ten months. https://betakit.com/toyo-raises-seed-funding-to-further-develop-openclaw-for-founders-tool/

### B. Best Python option: Pipecat
- [V] v1.11.0 released today (1.9/1.10/1.11 within 8 days), BSD-2, 15.6k stars, 343 open issues. https://github.com/pipecat-ai/pipecat/releases
- [V] Broadest transports: serializers for Twilio, Telnyx, Plivo, Exotel, Vonage, Genesys; WebSocket server, FastAPI WebSocket, SmallWebRTC, Daily, LiveKit, WhatsApp. S2S: Gemini Live (AI Studio + Vertex), OpenAI Realtime/GPT-Live, Nova Sonic, Ultravox, Grok. Google STT/TTS/LLM; 35+ STT vendors. https://docs.pipecat.ai/server/services/supported-services · https://github.com/pipecat-ai/pipecat/tree/main/src/pipecat/serializers
- [V] **Flows** (in core since 1.5.0; old repo archived 2026-07): node graph, per-node prompt + tools, transitions decided in our handlers — exactly "LLM proposes, code disposes". **Does not support S2S models** (Gemini Live, OpenAI Realtime): text LLM in an STT→LLM→TTS pipeline only. https://docs.pipecat.ai/guides/features/pipecat-flows · https://pypi.org/project/pipecat-ai-flows/
- [V] **Pipecat Evals**: YAML scripted or persona-simulated scenarios; asserts function calls with arguments, phrases, latency budgets, barge-in, LLM-judge; text mode or audio mode (synthesised caller, audio files); `pipecat eval run`. Tests Pipecat bots only. https://docs.pipecat.ai/pipecat/evals/overview
- [S] Smart Turn v3: 23 languages, Spanish yes; **Catalan, Galician, Basque no**. https://www.daily.co/blog/announcing-smart-turn-v3-with-cpu-inference-in-just-12ms/
- [V] Pipecat Cloud: $0.01/min (agent-1x), "unlimited concurrency", PSTN dial-in $0.018/min, Krisp VIVA free for 10k min/mo. https://www.daily.co/pricing/pipecat-cloud/
- [S] Pain points: breaking-change churn (1.10 moved to openai 3/httpx2; a 1.1→1.11 upgrade audit lists silent behaviour changes); Flows could freeze when interrupted during a function call (fixed by flipping `cancel_on_interruption`); VAD false triggers on noise and "mhm". https://github.com/juspay/clairvoyance/pull/1159 · https://dev.to/kollaikalrupesh/hardening-pipecat-a-month-of-fixing-what-matters-44l

### C. Other open source
- **TEN Framework** [V] 11.1k stars, licence not plain SPDX (Apache-2.0 with extra restrictions), 0.11.72 today after a 7-week release gap. [S] Graph runtime in Docker, transport leans on Agora, SIP via extension. [I] Slowest time-to-first-call here. https://github.com/TEN-framework/ten-framework
- **Vocode** [V] abandoned: last release 2024-08, last push 2024-11. https://github.com/vocodedev/vocode-core · **FastRTC** [V] stalled: last release 0.0.34 on 2025-11-24, last push 2026-01; Python/Gradio. https://github.com/gradio-app/fastrtc
- 2026 arrivals: Dograh ([V] BSD-2, 5.7k stars, visual builder on Pipecat), Bolna ([V] MIT, daily releases, India-focused) — not evaluated. OpenAI **GPT-Live** full-duplex model already wired into LiveKit 1.8.1 (`DuplexModel`), Pipecat and jambonz [V by release notes/docs] — not evaluated.

### D. Managed platforms — benchmark only (entry-tier concurrency vs "ten at once")
| Platform | Entry-tier concurrent calls | Source |
|---|---|---|
| ElevenLabs Agents | Free 4 · Starter 6 · Creator 10 · Pro 20 (burst ×3 at double price) | [S] https://help.elevenlabs.io/hc/en-us/articles/31601651829393 |
| Ultravox | 5 without a subscription | [S] https://docs.ultravox.ai/gettingstarted/concurrency |
| LiveKit Cloud-hosted agents | Build 5 · Ship ($50) 20 | [V] https://livekit.com/pricing |
| Vapi | 10 by default (zero headroom), +$10/line/mo; over-limit inbound is blocked | [S] + [V behaviour] https://docs.vapi.ai/calls/call-concurrency |
| Deepgram Voice Agent API | PAYG up to 15 | [S] https://deepgram.com/learn/tripling-default-concurrency-to-power-the-voice-ai-economy |
| Retell | 20 free, $8/extra slot | [S] https://www.cekura.ai/blogs/retell-ai-pricing-per-minute |
| Pipecat Cloud (hosting our own bot) | no stated cap | [V] https://www.daily.co/pricing/pipecat-cloud/ |
Not researched in the timebox: Bland, Synthflow, Hume EVI, Microsoft Voice Live, Nova Sonic. [I, unverified] Voice Live rides Azure Speech, one of the few stacks with Catalan/Galician/Basque STT and TTS; Hume EVI and Nova Sonic are unlikely to cover Galician/Basque.

## Comparison table (own-the-orchestration candidates)
| Option | Lang | Code-owned state + tool gating | Gemini Live / Google from this runtime | Ingress | 10 calls on entry tier | Health · licence | Time to first call |
|---|---|---|---|---|---|---|---|
| Custom Node edge + `@google/genai` | TS | Total (we write it) | Native; Vertex or AI Studio | Anything we adapt: WS, HTTP, phone media streams | Vertex 1,000 sessions [S]; AI Studio not guaranteed [V] | Google SDK; our code | 2–4 h |
| LiveKit Agents JS 1.9 | TS | High: tools, tasks, handoffs in code | Gemini Live + Gemini LLM yes; Cloud STT (Chirp) no | WebRTC, SIP only | Self-hosted worker yes [I]; cloud-hosted Build = 5 [V] | Weekly · Apache-2.0 · follows Python | 1–2 h (phone/SIP) |
| OpenAI Agents SDK TS 0.18 | TS | High: tools, guardrails, handoffs | None (OpenAI only) | WS, WebRTC, SIP, Twilio, Cloudflare | Not found | Weekly · MIT | ~1 h (Twilio/SIP) |
| jambonz + Node SDK | TS | High via toolHook/eventHook | Gemini Live via `llm` verb | SIP/PSTN only | Self-host: yes; hosted: not found | Active · MIT | 1–2 h hosted; self-host risky |
| Cloudflare `withVoice` | TS | Total (`onTurn` is ours) | None; no gl/eu STT listed | WS, Twilio/Plivo/Telnyx | Not stated | Beta, breaking · MIT | ~1 h (English/Spanish only) |
| Mastra voice | TS | n/a (not an orchestrator) | Provider with open bugs | none | n/a | Active | — |
| **Pipecat 1.11** | Python | High; Flows for cascaded only, not S2S | Gemini Live (AI Studio+Vertex), Google STT/TTS/LLM | Widest: 6 telephony serializers, WS, FastAPI WS, SmallWebRTC, Daily, LiveKit | Self-host yes; Pipecat Cloud no stated cap | ~Weekly, breaking churn · BSD-2 | <1 h |
| TEN | Py/Go/C++ | Graph config | Extensions | Agora RTC, WS, SIP ext. | Self-host | Irregular · hybrid licence | 4 h+ |

## Recommendation
**Principle: the brain is the product; the voice edge is a swappable adapter.** Build a transport-agnostic TypeScript "call brain" — explicit state machine, zod-validated tools, pre-write checks, an append-only ledger that alone produces the "what we did" report (never the LLM), and an event bus feeding the live dashboard and OpenTelemetry. This is what the leaderboard scores and what the jury means by "what you built around".

**First choice — custom Node voice edge on Gemini Live (Vertex AI) driving that brain.** Evidence, not taste: it is the only TS option that fits every harness contract; Gemini Live covers all five languages with automatic mid-call switching [V]; Vertex gives real concurrency headroom [S]; it spends the credits the team already holds; and with an S2S model the big frameworks add least (Pipecat Flows does not support S2S [V]; Smart Turn lacks ca/gl/eu [S]; Gemini does VAD and barge-in server-side [V]). Tool gating with S2S is done by the brain rejecting out-of-state calls and returning a corrective instruction.

Per harness contract:
| Harness turns out to be | Voice edge |
|---|---|
| WebSocket / HTTP audio, or a starter-kit protocol | Custom Node edge. Fallback: Pipecat WebSocket transport with a custom serializer. |
| Phone number (PSTN) | **LiveKit Agents JS** on a self-hosted worker + LiveKit Cloud SIP + a Twilio/Telnyx trunk (Krisp, turn detector, recordings for free) — or carrier media streams into the custom edge if it already works. |
| SIP URI | LiveKit Cloud SIP endpoint + Agents JS. Zero-infra fallback: OpenAI Realtime SIP via Agents SDK TS (OpenAI-only). |
| WebRTC | LiveKit Agents JS. |
LiveKit wins the phone/SIP/WebRTC rows on evidence: every other TS candidate is beta (Cloudflare), single-vendor (OpenAI SDK), telephony-only and self-hosted (jambonz), not an orchestrator (Mastra) or gone (Layercode, Vocode).

**Runner-up — split: thin Pipecat (Python) voice edge + the same TS brain over HTTP/WS.** Sane for a weekend if the edge stays under ~150 lines with zero business logic: Pipecat function handlers proxy `POST /calls/:id/tool` and stream events to the brain (same host, ~1–5 ms). Pin `pipecat-ai==1.11.0`. Trigger it when (a) the starter kit is Pipecat/Python, (b) the Node edge has no clean call by hour ~4, or (c) practice cases show S2S tool-calling is too loose and we need a cascaded pipeline (Flows-style gating, Smart Turn, Google/Azure STT with ca/gl/eu). Cost: a second runtime to deploy and debug at 3 am.

**What TS costs us versus Pipecat (plainly):** ready-made telephony serializers and WebSocket server (decisive while the harness is unknown); Flows; Pipecat Evals with audio mode — the best off-the-shelf answer to "how do you know your agent works"; Smart Turn; 35+ swappable STT vendors (LiveKit JS has no Chirp STT); Krisp on Pipecat Cloud; and roughly 1–3 hours of time-to-first-call. On merit Pipecat is the strongest framework for this brief; Python is the only reason it is not first.

**Avoid:** Vocode and FastRTC (dead/stalled); Layercode (pivoted); TEN (Agora-centric, hybrid licence, slow start); Mastra voice and Cloudflare `withVoice` as the core (use Cloudflare for the dashboard instead); any managed platform as the core — the team chose to own it, the jury grades what is built around the model, and ElevenLabs free (4), Ultravox (5) and LiveKit-hosted Build (5) fail "ten at once" outright while Vapi (10) has zero headroom. Do not deploy the worker to LiveKit Cloud Build, and do not route STT/TTS through LiveKit Inference on Build (5 connections).

## Hackathon fast-path (working call in under 2 hours)
1. 0:00 — register, read the starter kit, classify the contract with the table above. If the kit already ships a talking agent, keep its edge and bolt our brain behind its tool calls.
2. 0:15 — brain skeleton: `CallSession` state machine, tool registry (zod), ledger, SSE event stream; Vitest text-mode tests against the published practice cases from minute one.
3. 0:30 — edge: `ai.live.connect` on Vertex with tools, system instruction, input/output audio transcription, VAD config (`silenceDurationMs` 500–800), session resumption. Forward caller audio as `audio/pcm;rate=<native>`; on `toolCall` → brain → `sendToolResponse`; on `interrupted` → flush playback (Twilio `clear`). Phone leg: mu-law decode in, 24 k → 8 k low-pass + decimate + mu-law out, 20 ms frames (160 bytes).
   Phone/SIP contract instead: LiveKit Node agent starter, google `realtime` model, self-hosted worker, inbound trunk + dispatch rule, `krisp_enabled`.
4. 1:30 — ten-at-once smoke test: 10 parallel synthetic callers (WAV over WS) against Vertex; add a silence watchdog that reconnects via session resumption (known audio-freeze bug).
5. Saturday noon gate: run S2S against the practice answers; if tool-calling or refusals are loose, switch that edge to cascaded (LiveKit JS pipeline or the Pipecat split). The brain does not change.

## Gaps
- Harness contract, the starter kit's language/framework, and whether the "key" is a voice model or a records API — decides every row above.
- Not verified: Vertex 1,000-session limit for Gemini 3.8 Live specifically; whether Live API tools/system instruction can change mid-session (decides gating design); LiveKit JS parity for OTel, adaptive interruption and tasks; whether Build-plan caps touch self-hosted workers; jambonz.cloud trial; OpenAI realtime session limits on low tiers; gpt-realtime and Gemini Live actual quality in Galician/Basque over 8 kHz noise (measure, do not assume).
- Not researched: Bland, Synthflow, Hume EVI, Microsoft Voice Live, Nova Sonic, Deepgram/ElevenLabs language coverage; carrier trial-account concurrency (telephony probe).
- WebFetch summaries were produced by a small model; release years it printed were wrong and were corrected against the GitHub API. Re-check any number before spending money on it.
