# Voice models and the LLM — S2S vs cascade vs hybrid (research probe, 2026-09-18)

Status: research note, timeboxed ~20 min. Evidence marks: **[V]** verified = primary source fetched this session (several pages were read through an LLM page-summariser — spot-check a number before quoting it to the jury); **[S]** strong = credible secondary sources or search snippets of primary docs; **[I]** inferred = my reasoning. "Not found" is a finding.

## Question
Should the core be a native speech-to-speech (S2S) model, a cascaded STT→LLM→TTS pipeline, or a hybrid — and which LLM makes the decisions?

## Decision it informs
Central model architecture and primary LLM vendor. Team-lead constraints folded in: leaderboard-first (controllable beats natural-sounding); Google credits (largest) + OpenAI key + $100 for anything else, eval runs included; APIs only (no self-hosted GPUs); TypeScript/Node (`@google/genai`); team owns orchestration. A non-Google/OpenAI model must clearly beat them to justify a new account.

## Findings

### A. Benchmarks: tool calling and instruction following over long calls
1. **[V]** aiewf-eval (Kwindla Kramer/Daily; 30-turn tools + instructions + KB; README updated 2026-08-22). Voice-speed text LLMs: gemini-3.6-flash (minimal) 97.1% turn pass, TTFAT 798/984 ms P50/P95; claude-haiku-4-5 98.0%, 637/1615; gpt-5.1 98.0%, 739/1492; gpt-4.1 96.3%, 536/1771. S2S: gpt-realtime-2.1 (low) 97.2% (N=900), V2V median 1504 ms; grok-voice-think-fast-1.0 95.3%, 2336 ms; gpt-realtime-1.5 93.3%, 1152 ms; gemini-3.1-flash-live 91.7% (minimal, 1632 ms) → 96.0% (medium, 2400 ms; tool-turn V2V mean 3.2–3.9 s). **Gemini 3.8 Live and 3.8 Flash are not benchmarked yet.** Author's bars: LLM TTFAT ≲ 700 ms, V2V < 1500 ms, cascade V2V ≈ TTFAT + ~500 ms. https://github.com/kwindla/aiewf-eval
2. **[V]** Small/fast models fail it: gemini-3.5-flash-lite 68.6% (28% KB errors), gpt-5-mini 83.7%, gpt-4.1-mini 85.3%, gpt-oss-120b on Groq 86.3% (98 ms), gpt-5.4-mini removed for calling `end_session` early. **[I]** Per-turn errors compound: 0.917^10 ≈ 42% flawless 10-turn calls vs 0.971^10 ≈ 74%.
3. **[V]** τ-voice (Sierra; noise, accents, G.711 μ-law, interruptions): text reasoning ceiling ≈ 85%, GPT-4.1 text 54%; best S2S retains ~79% of text capability; top failure modes = misheard names/emails, noise, accents, turn-taking. No cascade-vs-S2S head-to-head published. https://sierra.ai/blog/tau-voice-benchmarking-real-time-voice-agents-on-real-world-tasks
4. **[V]** Artificial Analysis S2S leaderboard (Sept 2026; index = Big Bench Audio + Full-Duplex-Bench + τ-voice): Gemini 3.8 Live Extended Thinking (High) #1 at 82.6, τ-voice 68.6%; **plain Gemini 3.8 Live τ-voice only 30.1%**; Grok Voice Think Fast 2.0 81.3 / 56.5%; gpt-realtime-2.1 High 73.9 / 45.7%. https://artificialanalysis.ai/speech-to-speech
5. **[I]** Read together: on clean audio the best S2S models now match text LLMs at tool calling (~97%); the gap reopens on noisy, policy-heavy tasks (30–69% vs ~85% text-only). No public evidence that a cascade closes that gap — STT errors on a noisy 8 kHz line hit a cascade too. What a cascade still clearly wins: determinism, exact logs, text replay, per-language vendor choice.

### B. Google path (deep dive)
6. **[V]** Live line-up: `gemini-3.8-live` (default; released 2026-09-15), `gemini-3.8-live-extended-thinking` (thinkingLevel low/medium/high, no minimal), `gemini-3.1-flash-live-preview` (legacy), `gemini-2.5-flash-native-audio-preview-12-2025` (2.5 family shuts down Oct 2026). **No half-cascade Live model remains**; native audio outputs AUDIO only; no structured output, no caching. https://ai.google.dev/gemini-api/docs/live-api/capabilities · https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live
7. **[V]** Tool calling: 3.8 Live = async (`NON_BLOCKING`) by default, `behavior: BLOCKING` still available, scheduling SILENT / WHEN_IDLE / INTERRUPT. **Extended Thinking = async only** (no blocking, no scheduling); `turnComplete` no longer means idle — watch `interaction_status` IN_PROGRESS/IDLE. Tool responses are always manual. (The separate tools page still says "synchronous only" — docs are inconsistent three days after launch.)
8. **[V]** 3.8 Live: proactive audio is permanently on (`proactive_audio:false` errors) — the model may decide not to answer; affective dialog removed. **[I]** Direct risk against "silence is always wrong" on a noisy line → needs a no-response watchdog.
9. **[V]** Transparency: `inputAudioTranscription`, `outputAudioTranscription`; Extended Thinking adds `includeThoughts` summaries; `send_client_content` (user/model roles) works all session, so the orchestrator can inject state; `turn_complete=true` interrupts generation. **[I]** Transcripts are a side channel, not what the model "heard"; the auditable truth is tool-call args + server state.
10. **[V]** VAD/barge-in: `automaticActivityDetection` {startOfSpeechSensitivity, endOfSpeechSensitivity, prefixPaddingMs, silenceDurationMs, disabled}; manual `activityStart`/`activityEnd` for an own turn model; interruption cancels generation and keeps only audio already sent. aiewf runs Gemini in both server-VAD and explicit-activity modes.
11. **[V]** Sessions: audio-only 15 min (unlimited with `contextWindowCompression` sliding window); connection lifetime ≈ 10 min → `GoAway` → `sessionResumption` handle valid 2 h; 128k context; audio ≈ 25 tokens/s. https://ai.google.dev/gemini-api/docs/live-api/session-management
12. **[V]** Audio: 16-bit PCM, native 16 kHz in / 24 kHz out; "any sample rate can be sent", API resamples (docs still advise 16 kHz). **[S]** Field reports: naive per-chunk 8→16 kHz resampling adds artifacts (use a stateful resampler); carrier echo makes Gemini's VAD interrupt itself on SIP/Twilio; LiveKit bug — audio cut when a tool call ends the turn, because Gemini emits `toolCall` before the last audio chunks; 1008 errors when streaming input during a pending tool call (older models); forum thread on 2026 Gemini instability. https://discuss.ai.google.dev/t/gemini-live-api-acoustic-echo-cancellation-needed-for-sip-telephony-deployments/144332 · https://github.com/livekit/agents/issues/5742
13. **[V]** Languages: the Live docs table lists Spanish, Catalan (ca), Galician (gl), Basque (eu) among ~97 languages; auto-detect and mid-call switching; pin via system instruction. Quality in ca/gl/eu on a phone line: not found.
14. **[V]** Concurrency: the Developer API publishes no Live session cap. Google staff (Jul 2026): "we currently do not guarantee support for concurrent sessions because any limitations we have are on the tokens per minute basis"; real numbers only in the AI Studio dashboard. Tier 1 = billing linked (instant), spend cap $10 per 10 min; Tier 2 = $100 paid + 3 days. Vertex/Agent Platform: 1,000 concurrent sessions, 4M TPM per project. https://discuss.ai.google.dev/t/official-concurrent-session-rps-limits-for-gemini-live-api-where-are-they-documented/174664 · https://ai.google.dev/gemini-api/docs/rate-limits · https://firebase.google.com/docs/ai-logic/live-api/limits-and-specs
15. **[S]** EU: 3.1 Flash Live never reached Vertex (forum, 11 Sep 2026); Gemini 3.8 runs in `global` only, no EU residency (3.5 Flash is the newest with it). 3.8 Live on Vertex: not found. https://discuss.ai.google.dev/t/gemini-3-1-flash-live-preview-on-vertex-ai-eu-region-availability/144429
16. **[S]** Safety filters: adjustable per category; old complaints about medical content being blocked; Live-specific blocking of symptom talk: not found → run the "needs a doctor now" practice case early.
17. **[V]** Text Flash for a cascade: `minimal` thinking exists only up to gemini-3.6-flash / 3.5-flash(-lite); 3.7 and 3.8 Flash bottom out at `low` (**[S]** 3.8 Flash TTFT ≈ 13 s at default). The Google voice-loop LLM is therefore **gemini-3.6-flash, thinkingLevel minimal** ($0.75 / $3.75 per M, cached $0.075). gemini-2.5-flash needs thinking off, scores 89.9%, and dies in October. https://ai.google.dev/gemini-api/docs/thinking · https://ai.google.dev/gemini-api/docs/pricing

### C. OpenAI head-to-head
18. **[V]** gpt-realtime-2.1 (2026-07-06): configurable reasoning effort; "improved alphanumeric recognition, silence and noise handling, and interruption behavior"; p95 latency −25%. $32/$64 per M audio in/out (cached $0.40), text $4/$24; AA measures ≈ $10.75–11.31/h ≈ $0.18/min. Rate limits: Tier 1 200 RPM / 40k TPM, Tier 2 200k, Tier 3 800k TPM. https://developers.openai.com/api/docs/models/gpt-realtime-2.1
19. **[I]** Each response re-counts the session context: 10 calls × ~6 responses/min × 3–4k tokens ≈ 200k TPM → **Tier 1 will 429 on the ten-calls case**; needs Tier 2–3. Check the key's tier tonight.
20. **[V]** Languages: OpenAI lists Catalan and Galician but **not Basque** for gpt-realtime (unlisted languages: "quality will be low"). https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-language-support
21. **[V]** Developer reports after 2.1: 2.1-mini "stopped triggering function tools" over SIP; unsolicited narration; brittle on complex branching prompts. https://community.openai.com/t/new-realtime-models-on-the-api-gpt-realtime-2-1-and-gpt-realtime-2-1-mini/1385896

### D. Everyone else
22. **[S]** xAI Grok Voice Think Fast 2.0: $0.08/min (1.0: $0.05), 100 concurrent sessions per team, fastest TTFA (0.70 s). ca/gl/eu support: not found. https://docs.x.ai/developers/pricing
23. **[V]** Amazon Nova 2 Sonic: good tool/instruction scores but "a high rate of safety refusals for normal content" and an 8-minute connection limit (aiewf README). Bad fit for symptom talk.
24. **[S]** Ultravox: v0.7 (Dec 2025) still latest found; 86.7% on aiewf in Feb 2026, dropped from the current table; $0.05/min; free tier 5 concurrent calls. Mistral Voxtral: STT 13 languages / TTS 9, **no ca/gl/eu**; parts for a cascade, not an S2S agent. https://docs.mistral.ai/studio/audio/overview
25. **[I]** Moshi/Unmute, Sesame, Qwen3-Omni, Step-Audio, MiniCPM-o: self-host or no evidence of a hosted API with tools + es/ca/gl/eu → out under the APIs-only rule. Hume EVI, Microsoft Voice Live, Qwen realtime API: not researched (Voice Live wraps gpt-realtime + Azure STT/TTS, which do cover ca-ES/gl-ES/eu-ES — relevant to the STT/TTS probe).
26. Manipulation resistance: no public per-model voice benchmark found (only vendor runbooks: Hamming, Roark). **[I]** Treat every model as persuadable; enforce policy in code.

## Comparison — S2S models
| Model | aiewf pass · V2V | AA index · τ-voice · TTFA | es/ca/gl/eu | Control | 10 parallel, new account | ≈$/min | Verdict |
|---|---|---|---|---|---|---|---|
| gemini-3.8-live | n/a (3.1: 91.7%, 1.6 s) | 76.0 · 30.1% · 1.18 s | all four listed | async default, BLOCKING option, scheduling, state injection | TPM-based, undocumented; Vertex 1,000 | 0.014 | front-end config A |
| gemini-3.8-live-extended-thinking (High) | n/a (3.1 medium: 96.0%, 2.4 s) | 82.6 · 68.6% · 1.35 s | same | async only; thought summaries | same | 0.058 | front-end config B |
| gpt-realtime-2.1 | 97.2% · 1.50 s (low) | 73.9 · 45.7% · 1.21 s (High); 70.3 · 38.0% · 0.97 s (Minimal) | es, ca, gl — no eu | sync tools, reasoning effort, SIP | Tier 1 40k TPM too low | 0.18 | fallback front-end, non-Basque |
| gpt-realtime-2.1-mini | — | — · 29.4% · 4.28 s (High) | same | tool-firing bug reports | same | ~0.06 | avoid |
| grok-voice-think-fast-2.0 | 1.0: 95.3% · 2.34 s | 81.3 · 56.5% · 0.70 s | not found | — | 100 sessions | 0.08 | only outsider close; not clearly better |
| nova-2-sonic | tools 278/300, instr. 265/300 | BBA 88% · TTFA 1.14 s | ca/gl/eu not found | false refusals, 8-min cap | new AWS account | ~0.02 | avoid |
| ultravox v0.7 | 86.7% (Feb) | — | 42 langs; gl/eu not found | — | free tier: 5 | 0.05 | avoid |

## Comparison — text LLMs for the decision loop (aiewf-eval, [V])
| Model (setting) | Turn pass | Tool err | TTFAT P50 / P95 | Account | Verdict |
|---|---|---|---|---|---|
| gemini-3.6-flash (minimal) | 97.1% | 2.4% | 798 / 984 ms | Google credits | **first choice** — tightest tail of any frontier API |
| gpt-4.1 | 96.3% | 3.7% | 536 / 1771 ms | OpenAI key | runner-up: fastest P50, fat tail |
| gpt-5.1 | 98.0% | 2.0% | 739 / 1492 ms | OpenAI key | alternative |
| gpt-5.4 (low) · gpt-5.6-terra (none) · gpt-5.6-luna (none) | 97.0 · 91.3 · 88.3% | 3.0 · 8.1 · 11.7% | 782/1706 · 621/1870 · 671/2304 | OpenAI key | newer ≠ better here |
| claude-haiku-4-5 | 98.0% | 0.7% | 637 / 1615 ms | new account | best tool error, not a clear win → skip |
| claude-sonnet-4-6 · sonnet-5 · fable-5 (low) | 100 · 93.0 · 100% | 0 · 7.0 · 0% | 850/4126 · 1204/2465 · 3535/5148 | new account | tails too slow for a live loop |
| gemini-3.5-flash (minimal) · 2.5-flash (off) · 3.5-flash-lite | 93.3 · 89.9 · 68.6% | 5.3 · 9.1 · 30.8% | 892/1183 · 550/850 · 591/679 | Google | avoid (2.5 also shuts down in Oct) |
| gemini-3.7-flash · 3.8-flash | not tested | — | no `minimal`; multi-second TTFT | Google | offline analysis only |
| deepseek-v4-flash (low) · v4-pro (low) · glm-5.2 (none) · kimi-k2.6 (off), Baseten Model API | 96.7 · 97.3 · 99.7 · 93.9% | 2.8 · 2.7 · 0.2 · 6.0% | 677/1452 · 752/1477 · 936/2140 · 475/842 | new account | none clearly beats 3.6-flash |
| gpt-oss-120b (Groq) | 86.3% | 9.3% | 98 / 217 ms | new account | fast, fails the literal scorer |
Top open-weights rows (nemotron-3-ultra 100% / 541 ms, qwen3.8-27b 98.2% / 649 ms, gemma-4-31b 96.6% / 489 ms) ran on dedicated GPU deployments → excluded by the APIs-only rule. Llama 4 and Mistral text models: absent from the benchmark (not found).

## Latency
Cascade budget **[I]**, grounded in aiewf's "TTFAT + ~500 ms": transport in 30–80 ms · end-of-turn detection 250–500 ms (shorter = more cut-offs on a noisy line) · STT finalisation 50–250 ms (overlaps) · LLM TTFAT 550–800 ms · TTS first audio 100–250 ms plus 150–250 ms leading silence · transport out 30–80 ms → **≈1.1–1.6 s P50, 1.5–2.3 s P95** (gemini-3.6-flash ≈ 1.3 / 1.5 s; gpt-4.1 ≈ 1.05 / 2.3 s). Sub-second cascades need Groq-class LLMs that fail reliability.
S2S realistic **[V]**: 0.7–1.5 s non-tool turns (Grok 2.0 0.70 s; gpt-realtime-2.1 0.97–1.5 s; Gemini 3.8 Live 1.18–1.35 s), tool turns 1.5–3.9 s. **S2S no longer buys a decisive latency edge once reasoning is on.** A "thin S2S" relay (S2S calls a text brain every turn) stacks both: ≈2.5–3.5 s **[I]** → avoid as the general pattern.

## Cost (rough, per call-minute)
Gemini 3.8 Live ≈ $0.014 · Extended Thinking ≈ $0.06 · Grok 2.0 $0.08 · gpt-realtime-2.1 ≈ $0.18 (a 28-call scored run × 4 min ≈ $20) · own cascade ≈ $0.02–0.08 **[I]** (LLM $0.005–0.02 on 3.6-flash; STT/TTS prices not verified here). Text-only replay of 18 cases ≈ 0.9M input tokens ≈ $0.65 per suite on 3.6-flash **[I]** — evals are effectively free on Google credits; the $100 stays untouched unless a fallback is needed.

## Recommendation
**First choice — hybrid: Gemini 3.8 Live as ears and mouth, decisions and commits in our own code.** The voice model picks tools and phrases sentences; it never owns state. A server-side call state machine + validators own identity resolution, date resolution ("next Thursday" parsed in code against the scenario's "today"), clinic rules, availability and writes. Confirm-before-commit is enforced at the tool boundary (`propose_*` returns a proposal id + the read-back sentence; `commit_*` succeeds only for an identical, confirmed proposal). Refusal reasons come back from validators. **The end-of-call report is generated from server state, never from model prose.** Why this over a pure cascade, despite "controllable wins": (a) control lives in the tool layer in both designs; (b) five languages incl. Basque, barge-in and turn-taking come for free in one model on credits already held — in Node without a framework that plumbing would eat most of the 36 h; (c) clean-audio tool calling is now on par with text LLMs (finding 1); (d) minutes to a first call, and checkpoints pay for being early.
Run **both configs on the practice cases Friday night and pick by pass rate**: A = `gemini-3.8-live` with `behavior: BLOCKING` on commit-class tools (deterministic ordering, cheapest, best turn-taking, but τ-voice 30%); B = Extended Thinking at low/medium (τ-voice 68.6%, thought summaries for the jury, but async-only — it can talk before a tool returns). Prior: B for scoring, unless premature "you're booked" statements or invented slots show up.
**Runner-up and pre-built fallback — own cascade with gemini-3.6-flash (thinkingLevel minimal) on the same decision core.** Build its text half anyway as a "text twin": same prompt, tools and state machine driven by typed transcripts — it replays all 18 practice cases in seconds for ~$0.65, which is the fastest way to debug policy logic under a literal scorer, and it keeps the fallback warm. Switch a failing case class (or everything) to it if Gemini Live shows poor tool discipline, language drift, silence or instability. gpt-realtime-2.1 is the alternative S2S front-end (only S2S with published long multi-turn data: 97.2%) — but no Basque, ~13× the price, and Tier-1 TPM cannot carry ten calls.
**Two-phase plan:** Phase 1 (to first checkpoint) hybrid on Gemini Live — simple booking + ten-at-once on the board. Phase 2 (Saturday) text twin + A/B + hard cases (noisy line, languages, manipulation, refusals). Phase 3 (Sunday) jury polish: VAD/barge-in tuning, voice, live dashboard of transcripts + tool trace + state timeline + thought summaries.
**Avoid:** a "thin S2S" relay (latency doubles); gemini-3.7/3.8-flash, Sonnet/Fable in the live loop (seconds of TTFT); any lite/mini/nano or Groq gpt-oss model as decision-maker (68–86%); Nova 2 Sonic (false refusals, 8-min cap); gpt-realtime-2.1-mini (tool-firing reports, slow with reasoning); legacy Gemini 2.5/3.1 Live; opening new accounts for Grok/Haiku/DeepSeek — none clearly beats the Google options.

## Hackathon fast-path
1. Hour 0–1: starter kit call; read the harness contract (audio format, how the report is delivered, simulated "today"). Open 10 parallel `ai.live.connect()` sessions to test concurrency on the team's tier; check the OpenAI key's tier.
2. Hour 1–4: tool layer + state machine + report-from-state; Gemini Live session with `inputAudioTranscription`, `outputAudioTranscription`, `sessionResumption`, `contextWindowCompression`; log every event with timestamps per call id.
3. Line handling: stateful 8→16 kHz resampler; VAD start sensitivity LOW, `silenceDurationMs` ≈ 600–800 for the noisy line (or own VAD + `activityStart/End`); never cut playback on `toolCall`; no-response watchdog (no model audio N s after user stops → `send_client_content` nudge with `turn_complete=true`).
4. Accuracy levers from τ-voice failure modes: spell-back of names, DOB confirmation, fuzzy match against records, explicit disambiguation for the four-matches case.
5. Friday night bake-off: configs A vs B on the noisy-line, Basque/Galician/Catalan, manipulation and refusal practice cases; decide, then freeze the front-end.
6. Saturday: text twin regression suite in CI; only then prompt tuning.

## Gaps
- Gemini 3.8 Live is three days old: no independent multi-turn benchmark, no practitioner reports, docs inconsistent on async tools. **Biggest risk.**
- Actual concurrent-session/TPM limits for Live on the team's tier — undocumented; must be measured tonight. 3.8 Live on Vertex and any EU endpoint: not found.
- Real quality of Gemini Live (and any STT/TTS) in Catalan, Galician, Basque on 8 kHz noisy audio: no benchmark found — only practice calls will tell.
- Whether Live `safetySettings` interfere with symptom talk: not found.
- Cascade-vs-S2S under realistic audio: no published head-to-head (Sierra says pending).
- OpenAI: G.711 I/O, EU residency for Realtime and how TPM counts cached context were not re-verified this session; gpt-4.1 / Haiku prices not re-checked.
- Not researched: Hume EVI, Microsoft Voice Live, Qwen realtime API, Deepslate Opal (AA TTFA 0.44 s, index 62.1), tau2-bench text scores for Flash models, BFCL v4, VoiceBench.
- Harness contract still unknown (brief's gap) — if the endpoint is a phone number/SIP, Gemini Live needs a bridge while gpt-realtime has native SIP.
