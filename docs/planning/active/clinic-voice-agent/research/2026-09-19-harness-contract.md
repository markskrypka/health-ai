# Harness contract — what the organizers' docs actually require (2026-09-19)

Question: what exactly do we have to build, and how is it judged? · Decision it informs: the whole stack and build plan · Status: **verified** — read from the organizers' own docs, API spec and published cases, and confirmed with live calls to the clinic API using the team key.

Sources, saved verbatim in `docs/organizers/` (no secrets in any of them): the eight docs pages (`overview.md`, `challenge.md`, `quickstart.md`, `contract.md`, `clinic-api.md`, `rules.md`, `problems.md`, `api.md`) plus `normalization-table.md`, `openapi.json`, `public-cases.json` (73 cases with caller prompts and accepted answers) and `clinic.json` (the clinic catalogue). `extract-docs.cjs` re-extracts the pages from the dashboard bundle if they change. Credentials live only in `.env` (git-ignored).

## The task in one paragraph

We host **one WebSocket URL**. The harness connects to it and speaks **exactly Twilio's Media Streams format**, playing the carrier: `connected`, `start`, `media` (20 ms frames, 8 kHz µ-law, base64), `stop`. No phone number, no Twilio account, no telephony vendor. A simulated patient (an LLM with a persona, behind the harness's own speech pipeline) talks to our agent. During the call — or at the latest 30 seconds after the socket closes — our agent POSTs what it *would* have written to `POST /api/v1/submit/{register|book|reschedule|cancel|no-action|escalate}`. The clinic (`Clínica Arenal`, Madrid) is a **read-only** API; nothing is ever reserved. A case passes only if the list of submitted actions equals one of the case's accepted answers.

## The wire (verified, `contract.md`)

- `start.callSid` **is the `call_id`** for every submission — never mint one. `start.customParameters.from_number` is the caller's number in E.164 when not withheld: `GET /directory?phone=` finds the chart before the caller speaks. It is a hint, not identification, and the caller is not always the patient.
- `sequenceNumber`, `chunk`, `timestamp` are strings; keys are camelCase on the wire; `/submit/*` bodies are snake_case.
- We send `media` back on the same socket. `mark` and `clear` are accepted but **do nothing on their side**: turn-taking and interruption are entirely ours. Consequence: pace outbound audio in real time, so that stopping really stops.
- **Run All opens ten sockets at once**; the unscored Switchboard practice opens up to twenty. Everything is per socket. A refused or dropped connection fails that case.
- Harness host: AWS `eu-west-1` (Dublin); ~45 ms from the venue. Organizers recommend ngrok with a European region; any tunnel or host that forwards WebSockets works. The endpoint (and optional headers) is set by the team on the dashboard's Settings page and applies to the next run.

## Submissions (verified, `contract.md`, `openapi.json`)

- One request per action; identical action twice → `409` (a retry, harmless). After the window → `410`. Malformed → `422`. A `200` is receipt, not a pass. **Submitting nothing always fails** — a correct refusal is `NO_ACTION` with its reason.
- `book`: `patient_id`, `provider_id`, `location_id`, `appointment_type_id`, `slot` (explicit offset, exact minute, compared in Europe/Madrid), `policy_id`. `reschedule`: `appointment_id` + provider, location, slot, policy. `cancel`: `appointment_id`. `register`: given name, two surnames, `national_id` (check letter re-derived; a wrong letter is a 422), date of birth, phone, email, insurer. `no-action` / `escalate`: `reason`.
- Closed `reason` vocabulary (18): `not_eligible_age`, `referral_required`, `provider_not_in_network`, `specialty_not_covered`, `location_not_covered`, `insurer_referral_required`, `allowance_exhausted`, `provider_on_leave`, `location_hours`, `type_not_offered`, `patient_history`, `no_availability`, `clinic_closed`, `patient_not_found`, `provider_not_found`, `caller_not_authorised`, `out_of_scope`, `medical_emergency`.
- Ids are compared exactly. Tolerance exists only for registration fields and the slot (`normalization-table.md`): accents and case folded, surname order free, phone folded to nine digits, id dashes/spaces stripped, seconds truncated.

## Scoring and limits (verified, `rules.md`)

- Binary per case. Points = passed private cases × the problem's weight (1–5); **17 scored problems × 4 private cases = 68 calls, 196 points max**. The board ranks each team's **best** Run All. Problems open progressively (open now: 1–6; problem 2 is unscored).
- **The wall freezes Sunday 20 September, 06:00 Europe/Madrid.** Checkpoint windows are announced by the desk.
- **Every call is capped at three minutes.** No audible audio from our agent for the silence window → cut off and failed. Speed itself earns nothing.
- One queued or active run at a time; 30 s between practice calls; 15 min cooldown after a Run All finishes; a full Run All takes ~18 min → one every ~33 min.
- Practice calls (the `Call` button beside each published case) give the transcript, the recording and which fields lost. Scored cases reveal only pass/fail and a signal (`missing_record`, `record_mismatch`) until Monday.
- Not scored: voice quality, number of questions, model choice, speed. Exception — problem 14 checks our agent's transcript for the targeted patient's national id and phone (a substring check).

## The clinic (verified, `clinic-api.md`, `clinic.json`, live calls)

- Static and identical for everyone: 3 sites, 12 providers, 6 specialties, 11 appointment types, 10 plans, ~2,900 patients, calendar 7 Sep – 16 Oct 2026 in 15-minute slots. Cache the catalogue at start-up.
- `/directory`: `name` is fuzzy and returns `match_score`; **an exact field that does not match excludes the patient** (it filters). Records carry `has_visited_before`, `insurer`, `referrals`, a free-text `note`.
- `/availability` (window ≤ 14 days, `provider_id` or `specialty_id`, optional `location_id`, `patient_id`, repeated `insurer`): with `patient_id` it applies age, history and plans, **names the one correct `appointment_type`**, lists `payable_with` per slot, and names the rule that bit in `blocked`. Empty `slots` + empty `blocked` = simply full. A second plan is only ever found by asking the caller, then passing `insurer=`.
- Rules that are ours to apply: nothing same-day ("earliest" starts the day after the call); dates resolve against the moment the call connects, Europe/Madrid; morning is before 14:00; a weekday phrase means the first such weekday strictly after today; Monday 12 October is closed; only Centro opens Saturday; nothing opens Sunday; Sur shuts Friday lunchtime; Dr. Requena is on leave 14–30 Sep (move to the same specialty at the same site); near-miss names Sáez/Sáenz and Iglesias/Iglesia need a question; physiotherapist is "D. Álvaro Cid"; nearest site = smallest straight-line distance among sites that can serve the request (coordinates published).
- Language binds a booking only in problem 11: every provider speaks Spanish, four speak Catalan, some speak English.

## The 18 problems (weights) — `problems.md`

1 Simple Booking (1) · 2 Switchboard (unscored, concurrency) · 3 Doctor and Site (2) · 4 New Patient → `REGISTER` only (2) · 5 When Exactly, fixed date vocabulary (2) · 6 The Rules → `NO_ACTION(reason)` or redirected `BOOK` (3) · 7 No Slot Free (2) · 8 Change and Cancel (2) · 9 Third Party, book for the patient (3) · 10 Triage, published symptom table and five red flags → `ESCALATE(medical_emergency)` (3) · 11 Languages, Spanish/Catalan publicly, other languages of Spain privately (3) · 12 Noise, 5 dB SNR street/TV/room/car (3) · 13 Difficult Caller, book the *final* request (4) · 14 Adversarial → `NO_ACTION(out_of_scope)` and a clean transcript (4) · 15 Nearest Site (3) · 16 The Questions, wrong facts fail the booking (3) · 17 Second Policy, ask for it (4) · 18 The Real Call, multi-action under noise (5).

Published cases: 73, of which 65 are in **English** (with Spanish names, ids, emails), 3 Spanish, 1 Catalan; 7 have background noise. Every case ships the caller's full prompt, persona data, turn cap (18–40) and the accepted actions.

## What the organizers say to build first (`quickstart.md`)

Identification with a second identifier → the complete national id with its check letter → refusals with the right reason read off `/availability` → the exact minute with offset → the appointment type from the record → ten concurrent calls, nothing shared → turn-taking. They **recommend Pipecat** (Python): it ships a Twilio Media Streams serializer and transport. There is **no starter kit**.

## The jury, Sunday (`challenge.md`)

Added to the board score; weights announced by the desk: (1) patient experience — interruptible, repairs mishearings, never invents a slot, doctor or rule; (2) how personal — uses the chart note and history before asking; (3) the platform, shown live — how a call runs, what is visible in flight, "why did it say that?", ten concurrent calls; (4) safety and boundaries; (5) language used well; (6) engineering rigour — **own evaluation harness, variance across repeated runs, named failure modes, cost per call in money and seconds**; (7) discretion.

## What this changes in our earlier research

- No telephony vendor, no SIP, no phone number: the ingress question is closed.
- The clinic is Spanish but callers are mostly English-speaking; Basque and Galician matter only inside problem 11's private cases (12 of 196 points).
- The API already does eligibility, appointment type, coverage and restriction naming — our logic is orchestration around it plus the date, site and identity rules above.
- Published caller prompts + accepted answers make a text-level eval loop possible today, with the clock pinned to each case's `reference_time`.
- Pipecat's Twilio serializer matches this wire exactly; our "TypeScript, no framework" decision predates that fact and needs Mark's call.

## Gaps

The silence window length; checkpoint times; how the harness treats audio sent faster than real time; whether private problem-11 cases include Basque or Galician and how often; Gemini Live's real accuracy on dictated ids and emails over this line — only practice calls will tell.
