# Observability, evals and simulated callers — research probe

Date: 2026-09-18 · Timebox: ~20 min web research · Angle: see a call live, learn from it afterwards, know the agent works.
Legend: **[V]** verified (primary source fetched today) · **[S]** strong (several credible sources / primary seen only via search summary) · **[I]** inferred (my reasoning) · **[NF]** not found.
Caveat: pages were read through a summarising fetch tool; numbers and model IDs below should be re-checked at the moment of use.

## Question
What do we use to (1) see a call while it is happening, (2) learn from it afterwards, and (3) know that our agent works — within one weekend, in a TypeScript/Node codebase that owns its orchestration, Gemini first and OpenAI second?

## Decision it informs
Tracing/observability stack · live call console design · eval and simulated-caller harness.

## Findings

### A. Constraints that shape the pick
- Leaderboard = exact structured outcome per call, no partial credit; practice cases ship with answers; jury scores "what you can see while it is happening / learn afterwards / how you know your agent works" (brief). **[V]**
- So the unit under test is the **outcome payload**, not the conversation. Exact-match on outcome is the primary metric; LLM-judge is only for jury-facing quality. **[I]**
- "Ten at once" on a shared diary is most likely a race-condition test (double booking, state bleed). Every event/span/log needs a `callId`; the harness needs a concurrency mode. **[I]**
- Team is TS/Node and owns orchestration, so Python-only tooling (Pipecat Whisker/Tail/OTel, LiveKit simulations, fixa, audiomentations) is design inspiration, not a dependency. **[I]**

### B. LLM/agent tracing backends (state Sept 2026)
- **Langfuse**: Hobby free = 50k units/mo, 30-day retention, 2 users; datasets, experiments, LLM-as-judge, annotation all included on free; Core $29/mo (100k units, +$8/100k). **[V]** https://langfuse.com/pricing
- Langfuse TS SDK v4 is built on OpenTelemetry JS v2 (`@langfuse/tracing`, `@langfuse/otel`, `LangfuseSpanProcessor` on a `NodeSDK`). **[S]** https://langfuse.com/changelog/2025-08-28-typescript-sdk-v4-ga
- Langfuse attaches audio (wav/mp3/ogg) to observations via `LangfuseMedia` from `@langfuse/core`; free on Cloud while in beta. **[V]** https://langfuse.com/docs/observability/features/multi-modality
- Acquired by ClickHouse Jan 2026; MIT licence, pricing and self-hosting stated unchanged. **[S]** https://github.com/orgs/langfuse/discussions/11593
- **Braintrust**: Starter free = 1 GB processed data, 10k scores, 14-day retention, unlimited users, unlimited experiments/datasets/playgrounds; Pro $249/mo. Closed SaaS. **[V]** https://www.braintrust.dev/pricing
- **Laminar**: Apache-2.0, `docker compose up -d` self-host, TS SDK `@lmnr-ai/lmnr`, claims a "realtime engine for viewing traces as they happen"; cloud free = 1 GB, 7-day retention, 1 seat. 3.3k stars. **[V]** https://github.com/lmnr-ai/lmnr · https://laminar.sh/pricing
- **Pydantic Logfire**: free Personal plan 10M spans/logs/metrics per month; first-party TS SDK (`@pydantic/logfire-node`) that configures the OTel Node SDK. Generic OTel backend; eval features are Python-centric. **[S]** https://pydantic.dev/logfire · https://github.com/pydantic/logfire-js
- **PostHog LLM analytics**: Node wrapper `GoogleGenAI` from `@posthog/ai/gemini` (`posthogTraceId`, `posthogDistinctId`); generations auto-captured, **tool calls must be captured manually** as `$ai_span`. Free-tier size not verified. **[V]** https://posthog.com/docs/llm-analytics/installation/google
- **Arize Phoenix / OpenInference JS**: JS instrumentors exist for OpenAI, LangChain.js, Vercel AI SDK, BeeAI, TanStack AI — no `@google/genai` instrumentor listed. **[S]** https://github.com/Arize-ai/openinference/tree/main/js
- **Helicone**: acquired by Mintlify 2026-03-03, now maintenance mode (security/bug fixes only). Avoid. **[S]** https://www.helicone.ai/blog/joining-mintlify
- **OTel GenAI semantic conventions**: every `gen_ai.*` attribute still "Development" (not stable) as of mid-2026; moved to a dedicated repo in v1.42.0 (June 2026). Use the names, do not rely on stability. **[S]** https://opentelemetry.io/blog/2026/genai-observability/
- LangSmith, W&B Weave: not re-checked this session (timebox). LangSmith accepts OTLP (listed in Pipecat docs **[V]**); no TS/Gemini advantage found for a non-LangChain stack. **[NF]**

### C. Gemini and OpenAI tracing from TypeScript
- Langfuse's Gemini integration page shows **Python only** (`openinference-instrumentation-google-genai`); no JS path, no mention of Gemini Live. **[V]** https://langfuse.com/integrations/model-providers/google-gemini
- Braintrust has a TS wrapper `wrapGoogleGenAI` for `@google/genai` (streaming with TTFT, function calls traced); Gemini Live not mentioned. **[V]** https://www.braintrust.dev/docs/integrations/ai-providers/gemini
- Vercel AI SDK 7 is GA; Langfuse integration `@langfuse/vercel-ai-sdk` (stable at 5.9.0) + `LangfuseSpanProcessor`. Text-side Gemini calls through `@ai-sdk/google` therefore get auto-traced. **[S]** https://langfuse.com/changelog/2026-06-26-vercel-ai-sdk-7
- **No tool found that auto-traces a Gemini Live session.** Manual spans are required. **[NF]**
- Gemini Live server events usable as span/event sources: input transcription, output transcription, `interrupted`, `turnComplete`, `toolCall`, `toolCallCancellation`, `goAway`, `usageMetadata` (per-modality token counts), session resumption; input 16-bit PCM 16 kHz, output 24 kHz; VAD via `automaticActivityDetection`. Docs fetch listed models `gemini-3.8-live`, `gemini-3.8-live-extended-thinking`, `gemini-3.1-flash-live-preview` (legacy) — re-check IDs in AI Studio. **[V]** https://ai.google.dev/gemini-api/docs/live-guide
- OpenAI Agents SDK (TS): tracing on by default in Node; `RealtimeSession` runs are traced on the OpenAI side and the Traces dashboard shows audio in/out, tool calls, interruptions; custom `TracingProcessor` can forward elsewhere. OpenAI fallback therefore has better out-of-box voice traces than Gemini Live. **[S]** https://openai.github.io/openai-agents-js/guides/tracing/

### D. Framework-native tooling
- **Pipecat (Python)**: OTel tracing via `enable_tracing`, `enable_turn_tracking`, `conversation_id`; hierarchy Conversation → Turn → STT | LLM | TTS; attributes `metrics.ttfb`, `turn.was_interrupted`, `turn.duration_seconds`, token usage, `transcript`, `is_final`; documented exporters include Jaeger, Langfuse, LangSmith, SigNoz, MLflow, Datadog. Copy this span model. **[V]** https://docs.pipecat.ai/server/utilities/opentelemetry
- Whisker (frame-level debugger, `WhiskerObserver`, sessions saved to file, hosted UI needs ngrok) **[V]** https://github.com/pipecat-ai/whisker · Tail (terminal dashboard: logs, conversation, metrics, audio levels) **[S]** https://github.com/pipecat-ai/tail
- **LiveKit Agents**: test framework supports **Vitest (Node)** and pytest; text mode; Node API `session.run()`, `.nextEvent()`, `.isMessage()`, `.judge()`. "Simulations" (LLM-driven user, text or audio, on LiveKit Cloud) are **beta and Python-only**. **[V]** https://docs.livekit.io/agents/start/testing/
- LiveKit Cloud Agent insights: recordings + transcripts + traces + logs on all plans, 30-day retention; **traces stream during the session, transcripts/recordings upload after it ends**; needs LiveKit Cloud media servers; Node SDK >= 1.0.18. **[V]** https://docs.livekit.io/deploy/observability/insights/
- LiveKit agents-js → Langfuse works via `telemetry.setTracerProvider()`; caveat: do not pass `metadata` (OTel JS v2 removed `addSpanProcessor`). **[V]** https://langfuse.com/integrations/frameworks/livekit

### E. Voice-specific QA and simulation platforms
- **Cekura**: 300 free credits (~60 min), no card; then $0.25/min; 10 concurrent calls **[V]** https://www.cekura.ai/pricing · connects over WebRTC, SIP, WebSocket; 32 languages **[S]** (Cekura blog). Catalan/Galician/Basque coverage **[NF]**.
- **Coval**: Starter $100/mo = 100 sim minutes, 5 concurrent; 7-day trial **requires a credit card** **[V]** https://www.coval.ai/pricing · supports inbound/outbound calls and WebSocket endpoints **[S]** https://docs.pipecat.ai/pipecat/evals/platforms/coval
- **Hamming**: no public pricing, sales-led. Not viable in 36 h. **[S]**
- **Roark** (from $49/mo, built around replaying production traffic), **Evalion** (no self-serve), **Bluejay** (usage-based): none fits a pre-launch weekend. **[S]** (vendor comparison pages, weak sourcing)
- **fixa** (OSS, BSD-2, 117 stars): Python; needs Twilio + Deepgram + Cartesia + OpenAI; dials phone numbers. Last-commit date not verified. Borrow the design (persona + scenario + LLM evaluators), not the code. **[V]** https://github.com/fixadev/fixa
- Vapi Evals / Retell simulation testing: bound to their own platforms; irrelevant once orchestration is owned. **[I]** (not re-checked)

### F. Simulated callers and robustness evidence
- tau-bench **pass^k** = probability that all k i.i.d. trials of a task succeed (vs pass@k = at least one); GPT-4o went 61% pass^1 → ~25% pass^8 on retail. **[S]** https://arxiv.org/pdf/2406.12045
- **τ-voice** (Sierra, ICML 2026): 278 tasks, full-duplex, noise/compression/accents, voice user simulator decoupled from wall-clock; best voice agents retain ~79% of text-agent capability. Justifies two test levels. **[S]** https://arxiv.org/abs/2603.13686
- **EVA-Bench** (EMNLP 2026 Findings): bot-to-bot audio, validates the *simulator's* own errors and regenerates before scoring; accent/noise perturbation costs up to 31.4%; median peak-vs-reliable gap 0.44. **[V]** https://arxiv.org/abs/2605.13841
- **Google Cloud TTS**: Chirp 3 HD lists es-ES but **not ca-ES, gl-ES, eu-ES** **[V]** https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd · those three have Standard voices (`ca-ES-Standard-B`, `gl-ES-Standard-B`, `eu-ES-Standard-B`) **[V, list fetch was truncated]** https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types
- **Gemini native TTS**: auto-detects language; docs list Spanish, Catalan, Galician and Basque; models `gemini-3.1-flash-tts-preview`, `gemini-2.5-flash-preview-tts`, `gemini-2.5-pro-preview-tts`. Best single source for es/ca/gl/eu caller audio. **[V]** https://ai.google.dev/gemini-api/docs/speech-generation
- Audio degradation: Europe's PSTN uses A-law 8 kHz **[S]**; ffmpeg handles resample, band-pass 300–3400 Hz, `pcm_alaw`/`pcm_mulaw`, GSM only with a libgsm build. No ffmpeg filter for audio packet loss found — drop or zero 20 ms PCM frames in TS with a burst (Gilbert–Elliott) model. **[I]**

### G. Live-console transport
- **Convex** (sponsor): reactive queries over WebSocket are the core primitive; free plan ~1M function calls/mo, 0.5 GB DB. **[S]** (secondary pricing pages) https://docs.convex.dev/production/state/limits
- **Cloudflare Durable Objects** (sponsor): on the Workers Free plan since 2025-04; WebSocket hibernation; incoming WS messages billed 20:1; 100k requests/day free. More plumbing, no query layer. **[S]** https://developers.cloudflare.com/changelog/2025-04-07-durable-objects-free-tier/
- **Tinybird** (sponsor): free plan ~10 GB, 1k API requests/day; Events API over HTTP. Good for p50/p95 aggregates, not for the per-call live view. **[S]** (secondary)
- SSE from the Node voice server: zero dependencies, no persistence, single instance. Supabase Realtime: workable, not a sponsor, not checked. **[I]**

### H. What a voice-AI sponsor respects
- **Prosper's own words** (Aug 2026): "right-gates" cut EHR write hallucinations 10% → 1%; a real-time hallucination detector; QA on every call; a **flagged-calls dashboard** for selective review instead of auditing full logs; monthly drift rechecks. **[V]** https://www.getprosper.ai/blog/reliable-voice-ai-agent-healthcare
- Hamming OTel guide: root `call.lifecycle` → `turn.{i}` → `stt` / `llm` (+ `tool_call`) / `tts`; calls `stt.confidence` the highest-ROI attribute; goal is to classify a failure as bad audio / transcript / reasoning / tool side effect / speech / evaluation in under 10 minutes. **[V]** https://hamming.ai/resources/opentelemetry-voice-agents-tracing-guide
- Hamming latency guidance: time-to-first-word < 500 ms ideal, 800 ms acceptable; cascaded pipelines P50 < 1.5 s, P95 < 5 s; report p95/p99, never averages. **[S]** https://hamming.ai/resources/voice-ai-latency-whats-fast-whats-slow-how-to-fix-it

## Comparison table — tracing backends for a TS + Gemini team

| Tool | TS / OTel-JS | Gemini in TS | Free tier | Self-host | Live view | Evals in TS | Verdict |
|---|---|---|---|---|---|---|---|
| Langfuse | OTel-native SDK v4 [S] | via AI SDK or manual spans; no JS instrumentor [V] | 50k units, 2 users, 30 d [V] | MIT [S] | near-live (flush per turn) [I] | datasets, experiments, judge [V] | **First choice** |
| Braintrust | strong TS SDK, OTLP in [S] | `wrapGoogleGenAI` [V] | 1 GB, 10k scores, 14 d, unlimited users [V] | no (free) | near-live [I] | best-in-class `Eval()` [S] | **Runner-up** |
| Laminar | OTel-native TS SDK [V] | claimed; `@google/genai` not confirmed [V] | 1 GB, 7 d, 1 seat [V] | Apache-2.0 compose [V] | streams live [V] | SDK + CLI [S] | Swap-in if live spans matter |
| Logfire | TS SDK over OTel [S] | manual | 10M spans/mo [S] | no | live tail [S] | thin in TS [I] | Best pure OTel sink |
| PostHog | wrapper, OTLP in [V] | `@posthog/ai/gemini`; tools manual [V] | not verified | yes | events feed | online evals [I] | Only if already in PostHog |
| Phoenix | OpenInference JS [S] | no JS Gemini instrumentor [S] | OSS | yes | yes | Python-centric [I] | Skip |
| Helicone | proxy | — | — | — | — | — | Avoid: maintenance mode [S] |
| Jaeger/SigNoz | any OTLP | manual | OSS | yes | yes | none | Fallback sink only |

## Recommendation

**First choice — own the event log, export OTel on the side.**
1. One typed `CallEvent` stream emitted by the Node voice server is the source of truth. It feeds the console, the recording index, the post-call QA and the eval assertions. Nothing vendor-specific sits in the hot path.
2. **Convex** stores and fans out events (reactive queries → console with no WebSocket plumbing, TS end to end, sponsor). Batch-flush every ~250 ms; eval traffic writes JSONL plus a summary row only, to protect the function-call budget.
3. **OTel-JS → Langfuse Cloud** for the LLM-level "why": call → turn → stt | llm | tool | gate | tts spans, `gen_ai.*` names where they exist, `voice.*` custom attributes elsewhere, `callId` as session. Gemini text calls via AI SDK telemetry or 10-line manual generation spans; Gemini Live via manual spans from server events. Because it is plain OTLP, the sink is swappable in minutes (Logfire, Laminar, Jaeger).
4. **Home-grown TS eval harness** (tsx/Vitest), Gemini as simulated caller and as judge, exact-match on outcome, pass^k, a gate before every scoring run.

Why Langfuse wins on evidence, not popularity: OTel-native TS SDK, every eval feature on the free tier, audio attachments, MIT self-host as an exit. Known costs: 2 seats (share a login), 50k units (one 18×5 suite ≈ 3–4k units → budget $29 Core or trace only failing eval runs) **[I]**, no JS Gemini instrumentor.

**Runner-up — Braintrust** if the team wants the experiment-diff UI as the centrepiece: `wrapGoogleGenAI`, unlimited seats, the best TS eval DX. Costs: closed SaaS, 10k scores/mo cap (≈ 22 suite runs at 5 scorers) **[I]**, no audio story found.

**Avoid**
- Hosted voice-QA platforms as a core dependency: Hamming sales-led, Coval card-gated at $100/mo, all blind to the unknown harness contract and unproven on ca/gl/eu. Cekura's 60 free minutes are a reasonable *independent second opinion* on Sunday morning, nothing more.
- fixa, Pipecat Whisker/Tail, LiveKit simulations, audiomentations: Python-only. Exception: if the TS framework chosen is LiveKit agents-js, take its Vitest test helpers and free Agent insights.
- Helicone (maintenance mode). LLM-judge as the outcome metric (leaderboard is literal). Streaming per-frame audio or every STT partial into Convex.

## Live-console sketch (Next.js on Vercel + Convex `useQuery`)

Panels
1. **Call wall** — grid sized for 10 concurrent tiles: callId, language, state-machine state, elapsed, last utterance, last voice-to-voice ms, gate light, outcome badge.
2. **Timeline** — swimlanes caller VAD | STT | brain | tools | gates | TTS; per-turn latency waterfall `speech_end → stt_final → llm_first_token → tts_first_byte → audio_out`.
3. **Transcript with "why" drawer** — per agent turn: what it heard (text, language, confidence), state before/after, slots, tool args/results, gate verdicts, prompt version, model, deep link to the Langfuse trace.
4. **State and slots** — intent, resolved entities, candidate list (four matching patients → disambiguation status), vague-time resolution ("next Thursday" → ISO date against the clinic's "today").
5. **Outcome** — the exact JSON sent to the harness, per-field provenance (seq of the event that set it), harness response.
6. **Post-call QA + flagged-calls queue** — deterministic checks and judge rubric; mirrors Prosper's flagged-calls dashboard.
7. **Evals tab** — scenario × version matrix with pass^1 / pass^k, diff against baseline, flake list, git SHA.
8. **Health strip** — p50/p95 voice-to-voice, barge-in stop ms, stage error rates, concurrent calls.
Audio: write caller = left, agent = right into one WAV on a shared monotonic clock (pad silence); each turn stores its ms offset so clicking a turn seeks the player; attach the file to the Langfuse trace.

Events — envelope `{ callId, seq, tMs, turn?, traceId?, type, data }`
`call.started|ended` · `vad.speech_start|speech_end` · `stt.partial` (throttled) · `stt.final{text,lang,confidence}` · `turn.started|ended{interrupted}` · `llm.request{promptVersion,model}` · `llm.first_token` · `llm.response{text,toolCalls,usage}` · `tool.call|result{name,args,result,ms,ok}` · `state.transition{from,to,reason}` · `slot.updated{slot,value,sourceSeq}` · `gate.check{gate,verdict,reason}` · `tts.first_byte|done` · `bargein{stopMs,agentSpokenChars}` · `safety.flag{emergency|injection|policy}` · `outcome.submitted{payload,harnessResponse}` · `qa.score{check,pass,reason}` · `error`.
Latency truth: internal timestamps miss the network leg, so also compute voice-to-voice offline from the stereo file (gap between end of left-channel speech and start of right-channel speech). **[I]**

## Eval-harness sketch

Scenario spec (one file per practice case; `expect.outcome` copied verbatim from the organisers' answer)
```yaml
id: P07-vague-time
problem_type: vague_time            # one of the 18
source: practice-case-07
clinic_today: "2026-09-18T09:00+02:00"
persona:
  lang: es-ES
  facts: { name: "...", dob: "...", phone: "..." }
  goal: "book with Dr X next Thursday morning"
  behaviors: [interrupts_once, corrects_date]
  reveal: only_when_asked
audio:                               # level 2 only
  tts: gemini-tts                    # gcloud-standard as cheap fallback
  degrade: [alaw8k, babble_snr10, loss5_burst]
  bargein_at_ms: 1200
expect:
  outcome: { }                       # deep-equal after canonicalisation
  must_call: [lookup_patient, find_slots, book]
  must_not: [book_without_confirmation]
judge: [confirmed_details_back, right_language, refusal_reason_correct]
runs: 5
```
Runner — `pnpm eval --level text|audio --runs 5 --concurrency 10 --filter <id>`
- **Level 1, text**: Gemini persona (hidden facts sheet, stop condition) talks to the real brain through the real tool layer against a seeded clinic fixture reset per run. Seconds per case, runs on every change.
- **Level 2, audio**: caller text → Gemini TTS → degrade chain → streamed into the real endpoint exactly as the harness connects; both legs recorded to stereo; same expected outcome. Keep a pure black-box mode with no debug side channel.
- **Load mode**: 10 concurrent callers competing for the same slots; assert no double booking and no cross-call state.
- Scoring: exact-match outcome (primary) → tool-trace assertions read from the same `CallEvent` log → binary judge rubric with reasons (Gemini Pro-class, temperature 0, JSON schema, calibrated on ~10 hand-labelled transcripts) **[I]**.
- Simulator hygiene (EVA-Bench): detect caller-sim errors (leaked facts, off-script, early hang-up) and rerun rather than blame the agent.
- Report: console matrix + `eval-runs/<gitsha>-<ts>.json` + Convex Evals tab + scores pushed to a Langfuse dataset run. pass^k = all k of k runs pass.
- **Gate**: `pnpm gate` fails when any scenario's pass count drops below the accepted baseline; scoring runs happen only on green, tagged with git SHA and prompt version.

## Hackathon fast-path

First 2 hours (one person, parallel to the agent build)
1. `CallEvent` type + `emit()` in the voice server; JSONL per call as fallback (20 min).
2. Convex table + batched mutation + two queries: live calls, events by call (25 min).
3. OTel NodeSDK + `LangfuseSpanProcessor`; call/turn/llm/tool spans; flush at turn end (30 min).
4. Console v0: call wall + transcript/tool timeline + outcome JSON (30 min).
5. Three practice cases as scenario files + level-1 runner with exact-match diff (15 min once case format is known).

Friday night → Saturday morning: all practice cases as specs · runs=5 and pass^k · gate script · outcome provenance · stereo recording · "why" drawer.
Saturday: level-2 audio sim (es first, then ca/gl/eu) · degrade chain · barge-in and correction personas · 10-concurrent load test · latency waterfall and p95 strip · post-call QA and flagged queue.
Sunday morning: freeze · rehearse demo (live call on the wall → open the "why" drawer → replay a failed-then-fixed scenario → show the matrix) · optional Cekura free minutes and Tinybird aggregates.

## Gaps
- **Harness contract unknown** (endpoint type, outcome schema, simulated "today", practice-case format) — decides the level-2 transport, the canonicaliser and whether stage-level spans exist at all. Biggest risk to this plan.
- No auto-tracing for Gemini Live found; whether AI Studio's own logs cover Live sessions was not checked.
- Gemini TTS quality and accent realism for ca/gl/eu untested; Cloud TTS list fetch was truncated (es-ES row incomplete).
- LangSmith, W&B Weave, Supabase Realtime, Vapi Evals, Retell simulation: not re-checked. PostHog LLM-analytics free tier, fixa last-commit date, Laminar `@google/genai` TS support: not confirmed.
- Convex/Tinybird free-tier numbers come from secondary pages; sponsor perks may change them.
- Langfuse trace visibility delay and Hobby rate limits under 10 concurrent calls: not measured.
- Whether the chosen TS framework (custom vs LiveKit agents-js) exposes VAD and TTS first-byte timestamps: depends on the orchestration decision.
