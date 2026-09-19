# Contract — Clinic voice agent (HackSpain 2026, Prosper track)

Status: **DRAFT v3** — rewritten on 2026-09-19 against the organizers' docs (`research/2026-09-19-harness-contract.md`). Awaiting Mark's agreement.

## Goal

A simple voice agent that does exactly what the Prosper track expects: answer the harness's calls on one WebSocket, do the right thing against the read-only clinic API, and POST the exact actions each case accepts — plus an eval loop that tells us it works without phoning it again and again. Target: the highest best-Run-All score we can reach before the wall freezes on **Sunday 20 September, 06:00 Europe/Madrid**, and a call the jury enjoys on Sunday.

## Scope — in

1. **The call server**: FastAPI `/ws` speaking Twilio's Media Streams format through Pipecat; a fresh pipeline per socket; ten calls at once; never silent long enough to be cut off; every call under three minutes.
2. **The voice cascade, two keys**: Deepgram speech-to-text → Gemini Flash with tools → Deepgram text-to-speech; interruptible; English and Spanish heard and spoken. Catalan is best-effort (see `decisions.md`, 2026-09-19 "Fewer services").
3. **Agent logic, in code**: identification (caller id hint, name plus a second identifier, namesakes, relatives calling for a patient); slot search with the rules the API does not apply for us (nothing same-day, the fixed date vocabulary, closure day, site hours, doctor on leave, near-miss doctor names, nearest site); the appointment type and plan read off `/availability`; refusals mapped from `blocked` to the closed `reason` list; the published triage table and red flags; the second insurance plan asked for when the first does not cover; register / book / reschedule / cancel / no-action / escalate submissions, each validated against ids seen earlier in the same call; at least one submission per call.
4. **Evals without phoning**: a text-mode runner over all 73 published cases — simulated caller from the case's own prompt, same agent prompt, tools and model as production, clock pinned to the case, exact-match scoring under the published normalization, repeated runs for pass rate and variance, cost and seconds per call. Scripted practice calls through the dashboard for full-audio checks.
5. **Hosting**: ngrok on a laptop (EU region, static domain).
6. **A minimal live view** — transcript, tool calls, submitted actions and timings per call — once the open problems pass.

## Scope — out

A TypeScript build; speech-to-speech models; fallback pipelines; a third speech vendor (Soniox, ElevenLabs, Google Cloud speech); cloud deployment; telephony vendors; compliance work; tracing or analytics vendors; our own audio-level caller simulator; a Catalan, Galician or Basque voice (follow-up); anything production-grade.

## Success criteria

1. A practice call on "The Simple Booking" passes end to end through the real harness.
2. The text evals pass every published case of every open problem in at least 4 of 5 runs before a Run All is spent on measuring.
3. A Run All with ten concurrent sockets completes with no dropped or silent calls.
4. A scored run is on the board early on Saturday, and the best run improves as problems open.
5. Every call ends with at least one accepted submission.
6. On Sunday the jury can watch a call in the live view, and we can show the eval report with pass rates across repeated runs.

## Approvals

- Stack and approach: agreed by Mark on 2026-09-19 (see `decisions.md`).
- Scope as written above: pending Mark's yes.
