# Stack recommendation — cross-check of the eight probes (2026-09-18)

> **Status: partly superseded.** After reading this, Mark decided "keep it simple" (see `../decisions.md`, 2026-09-18): no fallback pipelines, no region hedge, no safety/compliance set, no tracing or analytics vendors, no spare telephony accounts, and the voice edge is chosen only after the organizers' docs are read. Use this note as the option map — one path per layer gets picked from it — not as the plan.

Question: which stack do we build the clinic voice agent on? · Decision it informs: every layer of the product · Inputs: the eight probe notes in this folder plus Mark's decisions in `../decisions.md`.
Marks: **[V]** verified by a probe on a primary source · **[S]** strong · **[I]** inferred. Probes read pages through a summarising fetch: re-check any number or model ID before spending money or code on it.

## The one idea all eight probes converged on

**The brain is the product; the voice edge is a swappable adapter.** A transport-agnostic TypeScript `CallSession` owns state, tools, checks and the report. Whatever listens and speaks sits in front of it and can be replaced without touching it. This is what the literal leaderboard scores and what the jury means by "what you built around it". Evidence: 78% of agent failures on τ²-bench are silent wrong-state writes and deterministic pre-write gates added +12.4 points [V]; "false success" is 45–48% of failures and LLM judges cannot see it [V]; Prosper's own blog credits "right-gates" with cutting record-write hallucinations from 10% to 1% [V].

## Recommended stack

| Layer | Pick | Fallback / runner-up | Why |
|---|---|---|---|
| Language, repo | TypeScript, Node LTS, pnpm monorepo | — | Mark's decision |
| Call brain | Own code: reducer + append-only event log, phase-scoped tools, Zod-validated dispatcher, pure pre-write gates with reason codes, `propose_*` / `commit_*` confirm-before-commit, `deriveOutcome(events)` with no LLM in it | XState 5 only if someone already knows it | Frameworks add LLM discretion, not transactional correctness [I]; Rasa CALM / Pipecat Flows are the same pattern in Python [S] |
| Voice edge (primary) | Custom Node `ws` server + `@google/genai` → **Gemini 3.8 Live as ears and mouth only** (hybrid). Bake-off: config A `gemini-3.8-live` with `behavior: BLOCKING` on writes vs config B `gemini-3.8-live-extended-thinking` | see next row | All five languages with auto-switch in one model [V]; turn-taking and barge-in server-side [V]; minutes to first call; on Google credits (~$0.014–0.06/min) [V]; control lives in the tool layer either way |
| Voice edge (pre-built fallback) | Cascade on the same brain: **Soniox `stt-rt-v5`** → **`gemini-3.6-flash`, thinkingLevel minimal** → **Google Chirp 3 HD** (en/es) + **Azure Neural** (ca/gl/eu; Google Standard-B as zero-account stopgap); Silero VAD in Node + STT endpoint events | `gpt-realtime-2.1` as emergency front-end (no Basque, ~$0.18/min, check the key's tier) | Soniox is the only STT verified with per-token language ID, all five languages, endpointing and μ-law in one stream, $0.12/h [V]; 3.6-flash minimal = 97.1% turn pass, 798/984 ms P50/P95 — tightest tail measured [V]; Azure is the only mainstream vendor with neural ca/gl/eu voices [V] |
| Side-channel LLM | `gemini-3.6-flash` (minimal): text twin, slot cross-check, urgency classifier, date-expression extraction, simulated callers; a larger Gemini for the offline judge | `gpt-4.1` / `gpt-5.1` | 3.7/3.8 Flash dropped `minimal` and take seconds to first token; lite/mini models score 68–86% [V] |
| Ingress | Decided by the harness contract. WebSocket → no vendor. PSTN → an existing aged account beats any choice; on new accounts **Plivo** (no documented concurrency cap, L16 16 kHz) with SignalWire/Vonage as spare (24 kHz L16 = zero resampling with Gemini); submit Telnyx L2 the same night. SIP → **jambonz cloud**. WebRTC → whatever the kit dictates | LiveKit Agents JS on a self-hosted worker if we want a framework for phone/SIP/WebRTC transport — it won that row on evidence [V] | Fresh Twilio accounts keep limited concurrency [V]; new Telnyx accounts cannot buy foreign numbers until L2, up to 48 h [V]; +34 numbers need ~72 h of documents [V] |
| Jury fallback | Browser "Call the clinic" page (PCM over WSS into the same edge) + a US number if the contract is PSTN | — | Works on any juror device; true wideband; keeps two paths live on Sunday |
| Data + realtime | **Convex**, EU West (region is irreversible): event log, state mirror, console queries, booking mutations if we own the data, outbox + watchdog via scheduled functions | Postgres partial unique index if Convex disappoints | Serializable OCC mutations remove slot locks [S]; scheduling is atomic with the mutation and scheduled mutations run exactly once [V]; sponsor |
| Console | Next.js on **Vercel** + shadcn/ui, Convex `useQuery` | — | Sponsor; never host the voice socket there (WebSockets beta, cut at max duration) [V] |
| Tracing | OpenTelemetry JS → **Langfuse Cloud** free tier; spans call → turn → stt/llm/tool/gate/tts, manual spans for Gemini Live | Braintrust (`wrapGoogleGenAI`), Logfire, Laminar — plain OTLP makes the sink swappable | OTel-native TS SDK, evals and audio attachments on the free tier, MIT self-host exit [V]; no tool auto-traces Gemini Live [V] |
| Analytics | **Tinybird** for post-call aggregates — later, never in the hot path | skip | Sponsor, Madrid company; free tier enough [S] |
| Evals | Home-grown TS harness: level 1 text personas (Gemini) against the brain; level 2 audio (Gemini-TTS personas in en/es/ca/gl/eu → ffmpeg A-law/μ-law 8 kHz + noise + dropped 20 ms frames) into the real endpoint; exact match on the derived report; pass^k; `pnpm gate` before every scored run; ten-concurrent load mode | Cekura's ~60 free minutes as an independent second opinion on Sunday | Hosted voice-QA platforms are sales-led or card-gated and blind to our harness [V]; Python-only tools are out |
| Hosting | **Cloud Run `europe-west1`** (min-instances 2, 4 vCPU / 4 GiB, concurrency 20, timeout 3600, no CPU throttling, session affinity) + the same image in `us-east4`; pick by measurement. Dev loop: Cloudflare Tunnel | Fly.io (`cdg`/`fra` + `iad`) or a GCE VM if the contract needs UDP (SIP/RTP/WebRTC) | Nothing we call is served from Madrid; vendor co-location outweighs caller proximity ~3:1 for a cascade [I]; on credits; never serve scored calls from a laptop |
| Safety | In code, not in the prompt: gates with no override path, verify-then-disclose, `find_patient` returns only `{matchCount, askNext}`, fixed emergency lines **pre-rendered as audio in five languages** (Gemini-TTS offline — its latency is irrelevant there), AI-disclosure greeting under ~8 s, silent-model watchdog, human-handoff outcome, red-team regression suite | — | EU AI Act Art. 50 applies since 2 Aug 2026 [V]; Gemini Live exposes no finish/safety signal and has silent-call reports [V]; never let the model author the emergency line |

## Conflicts between probes, and how they resolve

1. **Speech-to-speech vs cascade.** The orchestration and model probes pick Gemini Live as the edge; the speech probe picks a Soniox-led cascade and warns against Gemini Live as the whole pipeline; the safety probe adds silent-failure reports. Resolution: **hybrid first, cascade pre-built, decided by a bake-off on the practice cases.** Reasons: in both designs control lives in our tool layer; in Node without a framework the cascade's plumbing (VAD, endpointing, streaming TTS with cancellation, heard-position tracking) is 4–8 h that the hybrid gets for free; checkpoints pay for being early. Counter-evidence we accept: plain `gemini-3.8-live` scores only 30.1% on τ-voice (noisy, policy-heavy) while Extended Thinking leads at 68.6% and the text ceiling is ~85% [V] — hence the bake-off, the text twin, and the fallback. The speech probe's best idea survives in both designs: **two independent readings of slot-critical turns** (name, date of birth, date, phone) before any write — in the hybrid, Live tool args vs a text-model extraction from the transcript (Gemini's own `inputAudioTranscription` first; Soniox in parallel if that transcript is weak in ca/gl/eu).
   Switch rule: move a failing case class — or everything — to the cascade if the bake-off shows premature "you're booked", invented slots, language drift, silence, or instability.
2. **Vertex AI vs Gemini Developer API.** One probe says Vertex for its 1,000-session quota [S]; two say 3.8 Live is only on the Developer API's global endpoint and Vertex EU Live is the old, buggy 2.5 model [S]. Google staff: concurrent sessions on API keys are "not guaranteed", limits are tokens-per-minute [V]. Resolution: start on the Developer API with billing linked; **measure 10–12 parallel sessions in hour one**; the same SDK flips to Vertex with a flag if needed; if both cap out, the cascade needs no Live sessions at all.
3. **Madrid vs Belgium.** Madrid is closer to the venue, but no vendor serves from it. Resolution: Belgium plus a US hedge, chosen by measuring the harness's source IP.
4. **Pipecat.** On merit it is the strongest framework for this brief (telephony serializers, Flows, evals with audio mode) [V]; it is Python. Rejected per Mark's TypeScript decision. Revisit only if: the starter kit is Pipecat/Python, the Node edge has no clean call after ~4 h of work, or S2S tool discipline is too loose and the Node cascade is too slow to build — then a thin Pipecat edge (~150 lines, zero business logic) in front of the same TS brain.
5. **Denoising.** Enhancement before ASR made all 40 tested configurations worse [S]. Resolution: feed raw audio; denoise only the VAD branch if line noise causes false barge-ins.

## Measure in hour one (after the starter kit is read)

1. Ten to twelve parallel Gemini Live sessions on the team's key, two minutes of scripted audio each: errors, time to first audio.
2. Confirm model IDs in AI Studio (`gemini-3.8-live`, `gemini-3.8-live-extended-thinking`, `gemini-3.6-flash`) and that `BLOCKING` works on write tools.
3. Latency from `europe-west1` and `us-east4` to the harness and to the Gemini endpoint; log the harness source IP.
4. The "needs a doctor now" practice case through Gemini Live: any block or silence.
5. If the contract is PSTN: ten parallel inbound calls originated from a different account.

## Accounts to open (five minutes each)

Tonight: Google Cloud project with billing linked + Cloud Run; Convex (EU West); Vercel; Langfuse Cloud; Soniox — and request its concurrency raise now (default is exactly 10 connections) [V].
Only if the contract is PSTN/SIP: Plivo, SignalWire, jambonz cloud, Telnyx L2 submission.
Only when needed: Azure Speech (ca/gl/eu voices for the cascade).

## Top risks

1. **Harness contract unknown** — ingress, report schema, reason-code enum, simulated "today" and timezone, clinic API ownership, harness location. Every probe named it its biggest gap.
2. **Gemini 3.8 Live is three days old** — no independent multi-turn benchmark, inconsistent docs on async tools, undocumented concurrency, silent-call reports on its predecessors. Mitigated by the brain owning truth, the watchdog, the text twin and the cascade fallback.
3. **Catalan, Galician and Basque on a noisy 8 kHz line** — no independent benchmark exists for any vendor; Basque is weakest everywhere. Only practice calls will tell.
4. **Over-safety fails literal scoring** — a broad red-flag list or strict proxy rules turn ordinary bookings into refusals; a historic symptom must get one clarifying question, not an escalation.
5. **Scope vs 36 hours in one build stream** — the plan is tiered: leaderboard pieces first, jury pieces second, extras last.

## Gaps

The harness contract; real concurrency limits; ca/gl/eu quality; checkpoint times; sponsor perk amounts (`hackspain perk`). Not researched by any probe: Hume EVI, Microsoft Voice Live, Nova Sonic integrations, AssemblyAI/Cartesia Ink/Voxtral language coverage, Krisp.
