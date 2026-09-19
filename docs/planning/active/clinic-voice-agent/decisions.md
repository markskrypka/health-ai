# Decisions — Clinic voice agent

Newest first. Each decision carries its why.

## 2026-09-19 · Scored runs are fired by script, on the platform's clock, day and night
Decided by Mark (15:40). Why: rules 2.1 made the scored lane one call per problem with a 12-minute cooldown counted from the finish, a problem credits its first four passes, and scored calls pool — a scored call can only raise the score, so nothing is gained by a human deciding each one, and every idle quarter of an hour is a lost slot. `scripts/scored.py loop` owns both lanes: it fires the next scored call the moment the cooldown allows (heaviest owed problem first) and practises published cases in the gaps. Nobody else starts runs from the dashboard — the platform allows one queued or active run per team. Needs the laptop awake and online until the wall freezes, Sunday 06:00.

## 2026-09-19 · Commit after each verified fix, without asking; no pushes
Decided by Mark (15:40). Why: he wants a readable history and nothing lost if the session dies. Small commits on `clinic-voice-agent` after tests pass. There is no remote.

## 2026-09-19 · Points first; jury material once the open problems are banked
Decided by Mark (15:40). Why: scored slots are the scarce thing while we are 8th. The jury on Sunday judges what the board ignores — how the call sounds, interruptions, whether the clinic knows the caller, what we see live, what we learn afterwards, how we know the agent works, and ten calls at once — so a live call view, an eval report and a demo script follow, built in the cooldown gaps and after the freeze.

## 2026-09-19 · One voice per language; Catalan needs its own listening model (measured, not yet wired)
Why: on an 8 kHz line the English voice `aura-2-thalia-en` is understood at 96% of words and speaks a third faster than Deepgram's bilingual Spanish voices (86–88%), so one bilingual voice for the whole call was rejected; Spanish goes to `aura-2-carina-es` (99%). Deepgram Nova-3 `multi` has no Catalan and destroys Catalan dates ("dijous que ve al matí" → "Villosca de Almaty"); Nova-2 `ca` transcribes the same audio word for word. Pipecat can change both mid-call with a settings-update frame. Parked by Mark at noon for the scored runs; problem 11 "Languages" is not open yet.

## 2026-09-19 · Decisions are recorded during the call and POSTed when it ends
Why: an accepted action can never be withdrawn, and the evals showed a caller who changes their mind after "book it" producing `BOOK + BOOK` — a certain fail (problem 13 scores the FINAL request). The submission window stays open until 30 s after the socket closes, so nothing is lost by waiting. A later decision replaces the one it contradicts (same patient's booking, same appointment's move or cancel, any refusal once something is written; an escalation clears everything). Risk accepted: a crash mid-call loses the record — `finalize` runs shielded in the call's `finally`.

## 2026-09-19 · When the caller hangs up before the last tool call, send the likeliest answer
Why: silence always fails, so a guess is free. Order: a write the model spelled out as text but never called (a Gemini quirk seen in the evals: `default_api:register_patient{…}`) → the slot just offered, for the patient it was offered to → the reason the last search gave (`no_availability`, a blocked rule, `provider_not_found`) → `out_of_scope`.

## 2026-09-19 · Code checks what the API and the model cannot be trusted on
Why, each seen in a real or simulated call tonight: the directory API reports a shared surname as a name match (the child's name + the mother's caller id returns the MOTHER, flagged `name`+`phone`) → names are compared in code; the model filled a never-asked insurer with `privado` → `register_patient` refuses once when the caller never said that insurer; the model invented a weekday → the prompt forbids constraints the caller did not state, and `find_slots` takes `after_appointment_id` so "the next time after the one I have" needs no date arithmetic from the model.

## 2026-09-19 · End of turn is a silence timeout (0.9 s + VAD 0.2 s), not Pipecat's default model
Why: the default end-of-turn model closed the turn at "Hi." and after each group of a dictated DNI; a timeout keeps an id whole and behaves the same in every language. Plus one spoken holding phrase per caller turn when a lookup starts: the harness cuts a line that goes quiet.

## 2026-09-19 · Fewer services: Deepgram hears and speaks, Gemini decides — two keys
Asked for by Mark ("less services is better"); vendor picks revised by evidence. **Supersedes the Soniox and Google Chirp 3 HD picks below.** A cascade needs three functions — hear, decide, speak — and nothing below that without a speech-to-speech model; the vendors behind them collapse to two API keys, both plain keys (no Google Cloud service-account JSON, no Cloud Console):
- **Deepgram**, one key: Nova-3 streaming speech-to-text (`multi` = English + Spanish with code-switching) and Aura-2 text-to-speech (English voices; Spanish voices including Peninsular accents). Pay-as-you-go limits from Deepgram's rate-limit page, read 2026-09-19 through a summarising fetch: 150 concurrent streaming STT connections, 45 concurrent streaming TTS connections — room for the ten sockets of a Run All and the twenty of the Switchboard. Pipecat 1.11 ships `DeepgramSTTService` and the WebSocket `DeepgramTTSService` (both import cleanly here), plus a Flux service if we want Deepgram's own end-of-turn detection.
- **Gemini Flash**, one key, on the team's Google credits — unchanged.
- **Why not ElevenLabs** (Mark's example): per the 2026-09-18 speech probe its plans cap concurrent TTS at 2 / 3 / 5 / 10 (Free / Starter / Creator / Pro at $99), so ten simultaneous calls would need the whole €100; Deepgram's TTS comes on the key we already need for STT. A nicer voice for the jury's single call on Sunday is a one-line swap — a follow-up, not a second service now.
- **What this costs us, honestly:** Catalan. Soniox covered English, Spanish and Catalan in one model; Deepgram's `multi` does not include Catalan (it exists only as a separate single-language mode), and has no Galician or Basque. At risk: the Catalan share of problem 11 (the whole problem is 12 of 196 points). Refinement inside the same vendor, if time allows: switch Deepgram's language to `ca` mid-call once the agent notices Catalan. Catalan callers are answered in Spanish either way.
- Rough cost: ~$0.05 per two-minute call (≈ $0.0077/min STT, $0.03 per 1,000 characters spoken) → about $3.50 per full 68-call Run All on the €100 card, before any sign-up credit.

## 2026-09-19 · The stack, after reading the organizers' docs
Decided by Mark (framework, voice approach, scripting, hosting); component picks by evidence in `research/2026-09-19-harness-contract.md` and the 2026-09-18 probe notes. One path per layer, no fallbacks.
- **Python + Pipecat**, one service: FastAPI WebSocket `/ws` + Pipecat's `TwilioFrameSerializer` with `auto_hang_up=False` and no Twilio credentials; a fresh pipeline per socket. Why: the harness speaks exactly Twilio's Media Streams format and the organizers recommend Pipecat; turn-taking, barge-in, real-time audio pacing, µ-law and resampling come ready-made, so the hours go into agent logic and evals. **This supersedes "TypeScript / Node for the real-time backend" and "Node LTS + pnpm" (2026-09-18).** Tooling: Python 3.12, `uv`, a pinned `pipecat-ai`.
- **Cascade first**: speech-to-text → Gemini Flash with tools → text-to-speech. Why (Mark): exact text at every step, and the text evals exercise the very same LLM, prompt and tools as a live call.
  - STT: **Soniox `stt-rt-v5`** through Pipecat's `SonioxSTTService` — one model for English, Spanish and Catalan (plus Galician and Basque) with per-token language id, custom context terms (doctor, site and insurer names), µ-law telephony audio, ~250 ms finals with Pipecat's local VAD, about $0.12 per audio hour on the €100 card. Its default limit is exactly 10 concurrent connections: request a raise at sign-up, or round-robin two project keys. If practice calls show weak capture of dictated ids, the one-line swap to try is Deepgram Nova-3 (English/Spanish only).
  - LLM: **Gemini Flash with minimal thinking** through `GoogleLLMService` on the team's Google credits (`gemini-3.6-flash` per the 2026-08 voice benchmark: 97.1% turn pass, 798/984 ms). Confirm the exact model id against the API's model list before coding.
  - TTS: **Google Chirp 3 HD, streaming**, through `GoogleTTSService` on Google credits — English and Spanish voices of the same family, switched at runtime when the caller's language changes; generous concurrency compared with the 2–5 streams of entry-tier ElevenLabs or Cartesia plans. Catalan callers are understood in Catalan and answered in Spanish for now (no Chirp 3 HD Catalan voice); a Catalan voice is a follow-up.
  - Turn-taking: Pipecat defaults — Silero VAD + Smart Turn, interruptions on; an idle prompt so our side is never silent long enough to be cut off.
- **Agent logic in plain Python**: the LLM proposes, code disposes. Tools over the clinic API (`find_patient`, `find_slots`, `list_appointments`, `submit_*`); code owns date phrases, the DNI/NIE check letter, nearest site, provider-name resolution, leave fallback, and the mapping from `/availability`'s `blocked` to a `reason`; submit tools accept only ids that earlier tool results produced in the same call; every call ends with at least one submission.
- **Evals without phoning**: our own small text-mode runner — the caller is an LLM playing each published case's `caller_prompt`, the agent is the same prompt + tools + Gemini model as production, the clock is pinned to the case's `reference_time`, submissions are captured locally and compared with `expected.acceptable` under the published normalization rules; N repeats per case give the pass rate and its variance, plus cost and seconds per call. Full-audio checks use the organizers' practice calls, scripted through the dashboard API (`POST /leaderboard/api/problems/{id}/runs` with `case_id`; per-field results and transcript from `/submissions`).
- **Dashboard scripting allowed** (Mark): practice calls, results and the endpoint setting may be driven from scripts; credentials live only in `.env`. The endpoint currently registered belongs to a teammate's prototype — do not overwrite it without Mark's go.
- **Hosting: ngrok on a laptop throughout** (Mark) — EU region, static domain, laptop kept awake. Why: simplest; the harness is in AWS Dublin, ~45 ms away.
- **Minimal live view** from the same FastAPI app (live transcript, tool calls, submitted actions, per-turn timings; JSONL per call) — only after the open problems pass.

## 2026-09-18 · Keep it simple — a hackathon agent, not a production system
Decided by Mark, after the stack recommendation. Why: the track scores exact outcomes on 18 problems plus one jury call; fallback pipelines, region hedges, compliance work and durability machinery cost hours and score nothing. In: a simple voice agent that does exactly what the task expects, and automated evals. Out: fallback voice pipelines, multi-region hedging, safety/compliance work (EU AI Act, GDPR, HIPAA), pre-recorded emergency audio, red-team suites, tracing and analytics vendors, spare telephony accounts, browser call page. Note: urgent callers, refusals with a reason, proxy callers and manipulation resistance stay — they are among the 18 scored problems, not compliance extras. This supersedes the matching parts of `research/2026-09-18-stack-recommendation.md`.

## 2026-09-18 · Automated evals are in scope and are how we know the agent works
Asked for by Mark: no phoning the agent again and again. Approach: simulated callers in text drive the same agent logic (prompt, tools, state) as the voice path; each published practice case is a scenario; the check is an exact match on the report the agent would send — the same thing the leaderboard checks. If the organizers' docs allow triggering practice calls from a script, that is the full-audio eval; we do not build our own audio simulator unless the docs rule that out. Consequence for the voice edge: prefer the option where the text-mode eval exercises the same LLM, prompt and tools as the live call.

## 2026-09-18 · Voice edge and ingress: decide after the organizers' docs page is read
Decided by Mark. Why: the docs define how the harness reaches us and what the starter kit ships; choosing before reading them is guesswork. Telephony (the team has no existing account): needed only if the docs require a phone number or SIP address — then Plivo for a number (no documented concurrency cap on new accounts, 16 kHz streaming, Node SDK) or jambonz cloud for SIP; a WebSocket contract needs no telephony vendor at all. One account, no spares.

## 2026-09-18 · One build stream — no split by roles
Decided by Mark. Why: splitting by roles would make the actual building harder. The build plan is a single sequence of pieces, dependencies first and risk early.

## 2026-09-18 · Node LTS + pnpm monorepo; Claude Code is the only coding agent
Decided by Mark. Why: widest SDK compatibility and the least surprise during a scored run. Only `CLAUDE.md` carries the managed block — no `AGENTS.md`.

## 2026-09-18 · First checkpoint time unknown — plan for the earliest possible scored run
Why: Mark has not seen the checkpoint schedule yet; "being early pays", so the first build piece must end with a run on the leaderboard.

## 2026-09-18 · Leaderboard first; voice polish for Sunday
Decided by Mark. Why: scoring is pass/fail with no partial credit and both checkpoint prizes go to early leaders. Where a natural-sounding choice and a controllable choice conflict, controllable wins; polish comes once cases pass.

## 2026-09-18 · Budget: Google credits + OpenAI key + $100 from the organizers for any other API
Decided by Mark. Why: the organizers gave each team $100 for APIs. Extra vendors are allowed where the research shows a clear win; the $100 must also cover automated eval runs with real audio, so per-minute prices and concurrency limits matter.

## 2026-09-18 · APIs only — no self-hosted GPU models this weekend
Decided by Mark. Why: less to operate and fewer things to break during a scored run. Open-source models count only if someone hosts them behind an API.

## 2026-09-18 · Sponsor infrastructure preferred when competitive
Decided by Mark. Why: credits, on-site engineers, goodwill — but only when the sponsor product is as good as the alternative (Convex, Cloudflare, Vercel, Tinybird, Exa, fal.ai…).

## 2026-09-18 · Own the orchestration — no managed voice platform
Decided by Mark. Why: the jury explicitly judges "what you built around" the voice model — how a call is orchestrated, what we see live, what we learn afterwards. An open framework or our own code plus best-of-breed components keeps nothing a black box. Managed platforms (Vapi, Retell, ElevenLabs Agents…) stay in the research only as a benchmark.

## 2026-09-18 · Prefer Gemini / Google Cloud; OpenAI second
Decided by Mark. Why: the team holds a Gemini API key and an OpenAI key, with the most credits on Google AI / Google Cloud. Any other paid vendor must clearly beat the Google or OpenAI option for its component to justify a new account.

## 2026-09-18 · TypeScript / Node for the real-time backend
Decided by Mark. Why: it is the team's strongest language. Python only where it is overwhelmingly better, and then as a thin, isolated piece.

## 2026-09-18 · Sized as an Initiative; research depth Deep
Why: the work spans the whole hackathon weekend and several sessions; the stack question compares alternatives across vendors whose versions, pricing and limits move fast; Mark asked for no defaults-by-popularity (Twilio, LiveKit must earn their place or lose it on evidence).
