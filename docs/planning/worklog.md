# Worklog

Newest first. One entry per change, written when the change lands.

## 2026-09-19 · feat · the last two problems of the evening: the nearest clinic with directions, clinic facts turned round
By: Mark Skrypka
Why: at 21:00 the organizers opened "The Nearest Site" and "The Questions" (12 points each) and announced that the first team to reach the maximum wins the evening's prize. Their fresh docs showed two things ours could not do: a caller who asks how to get to the clinic hangs up on "I do not know", and a caller who asks about the clinic hangs up on one wrong fact. Our geocoder also failed on two of the three published addresses.
How: `geo.py` places the caller from a town outside the city, else the street through OpenStreetMap (asked as "street, Madrid" or street + city, which it answers; the old free-text query it did not), else a list of Madrid districts and landmarks — the published origins all resolve, mangled or not — and writes directions from the two coordinates. `tools.nearest_site(address, specialty)` works before identification and names the nearest clinic that has the doctor they need; `find_slots` then walks the clinics nearest first whatever site the model passes. `prompt._by_clinic` generates BY CLINIC and HOW MANY from the catalogue, negatives spelled out. Organizers' docs and cases refreshed. Verified: 95 tests; text evals 7 of 9 (both misses are cases whose published Saturday slot no longer exists); on the harness the scored calls used the tool, named Centro for gynaecology from Alcobendas and Sur for physiotherapy, and gave directions: "The Nearest Site" 4/4.
Ref: 713a073

## 2026-09-19 · fix · a later move keeps its doctor and clinic; "the next one" keeps the clinic
By: Mark Skrypka
Why: the reschedule path had never run live (all four change_and_cancel scored calls were cancels) and "The Real Call" (weight 5, not open yet) leans on it in 2 of 3 published cases: the move guard did not recognise "cannot make his appointment"/"no va a poder ir" and answered "book instead", and doctor and site were left to the model. Separately, the one no_slot_free scored miss: asked for "the next one" after 09:00 Sáez at Sur, we offered 09:15 Ortiz at Centro; twice the model also passed a slot ref as `after_appointment_id` and got an error.
How: `tools.find_slots`: `after_appointment_id` takes an appointment (keeps its doctor and site unless the caller named others, only later times, and marks the call as a move so `reschedule` is not questioned) or the slot just offered (keeps the site, any doctor). `_offer` lists later times at the first offer's site before other sites'. Move words for a relative's appointment. Prompt: offer the next in the list; a later move passes nothing about doctor or site; no goodbye while something asked for is still open. My first rule ("next keeps the doctor too") was refuted by a targeted text eval against today's accepted answer (another doctor's 09:30 at the same site) and corrected before deploy. Verified: 90 tests (6 new); text evals on exactly the touched cases — the_real_call 3/3 (6/6 on the first cut), the published later move 1/1, no_slot_free 4/4 against today's answers; deployed 20:20 with the line idle. Through the real harness at 21:07 (practice, the published later move): passed in 57 s — the model passed only the appointment id, the search came back pinned to Dra. Benítez at Norte, the move was not questioned. (A first dial at 20:55 failed `endpoint_unreachable`: the ngrok session dropped from 20:54 to 21:04 on a network timeout, same address after.)
Ref: 94a6817

## 2026-09-19 · fix · the line's own number always counts; a sound id forgives a mangled name
By: Mark Skrypka
Why: on a scored languages call "Alice Collins Davies" reached us as "Alys Davis"; her NIE was sound and on file and she rang from her own number, yet three lookups ended not_found and the call closed as patient_not_found at the wrap-up clock. The lookup that carried the NIE no longer carried the caller id (the model passes `use_caller_id` only with the first try), so the record had one exact detail and a name that did not agree. Confirmed against the live directory. The harness redialled her and the redial passed.
How: `tools.find_patient` adds the caller id to every lookup the caller gave a detail for, and retries without it whenever it finds nobody (a relative's phone); `_identifies`: a record found by a check-letter-sound DNI/NIE needs only one recognisable word of the name — a phone is shared by mother and child, an id is not; a corrected letter still needs the full name. Three regression tests (they fail on the old code); 86 pass; a local dry-run call booked the published answer in 64 s; deployed 19:35 with the line idle.
Ref: 59f3154

## 2026-09-19 · docs · the leader's repo read against ours
By: Mark Skrypka
Why: Mark asked whether cachopo's approach (1st at 18:30, 132 points to our 96) is better, why, and what would make ours smarter and more reliable.
How: their public repo cloned read-only to the scratchpad; four parallel probes (brain and write path, voice, deterministic helpers, readiness for problems 15–18) cross-checked against our code, 176 call logs and the live read-only API → `active/clinic-voice-agent/research/2026-09-19-competitor-cachopo.md`. Verdict: their lead was calls banked, not a better agent — during the read our loop took every open problem to 4/4 (148 points, rank 1 at 19:30). Worth taking: doctor and site pinned on a later move, slots bound to their patient, a refusal gate, nearest-site before identification. Not worth taking: immutable mid-call writes and the confirm-in-a-new-turn flow (12 of their 23 calls hit the wall).
Ref: 6cc92b6

## 2026-09-19 · feat · call console for the jury; the loop dials scored calls only; a night script
By: Mark Skrypka
Why: the jury judges "what you can see while it is happening" and "what you can learn from it afterwards"; the platform's queue grew to 10–15 minutes per run, so a practice call in a gap was costing a scored slot; and the tunnel and the loop lived inside the assistant's session, which would not survive the night.
How: `clinic_agent/console.py` + `console.html`, a separate read-only process on port 7870 over `logs/calls/*.jsonl` (live and finished calls, each call's timeline with lookups, offers, decisions and what replaced what, submissions, and the numbers of the last hours). `scripts/scored.py`: practice calls removed, a line check before each scored call (re-registers the endpoint if the tunnel's address changed, holds while the line is down). `scripts/night.sh`: server, a tunnel of its own, endpoint and loop in one terminal under `caffeinate`. Checked "The Real Call" (not open yet) in text on today's code: 3/3.
Ref: 4627ec1

## 2026-09-19 · feat · a voice per language, a Catalan listening model; a refusal takes back the booking it follows
By: Mark Skrypka
Why: "Languages" opened. On the deployed build the three Spanish cases passed practice, but the Catalan one either failed (the multilingual model heard "la data de naixement" as the name "Ana Xamen") or crawled to 236 s, the caller asking again and again what time we had said: an English voice reading Spanish is not understood. Separately, "No Slot Free" failed practice with BOOK + NO_ACTION after "okay … oh no, not mornings".
How: `languages.py` + `speech.VoiceRouter`: each sentence the model writes is spoken by the voice of its language (`aura-2-thalia-en`, `aura-2-carina-es`; measured 96% and 99% word match on an 8 kHz line), stock phrases follow; two Catalan words in what the caller said move the listening model to Deepgram Nova-2 `ca` by a settings update; the prompt allows replies in English or Spanish only. `find_patient`: two exact details on one record beat a mangled name. `_record`: a NO_ACTION replaces a booking for the same patient and kind of doctor, and is never recorded beside another action (true of all 73 published answers). Mark chose to finish on Deepgram rather than move to ElevenLabs (asked 16:05). Verified: 82 tests; local calls in English, Spanish and Catalan; the published Catalan case through the harness: passed in 117 s.
Ref: 7fda07d

## 2026-09-19 · feat · the scored lane on a clock, after the organizers changed the rules
By: Mark Skrypka
Why: rules 2.1 (19 Sep) replaced Run All with one scored call per problem, 12 minutes apart, four credited passes per problem, pooled. We held 40 points, 8th; problems 7–10 opened, worth 40 more; every idle cooldown is a lost slot.
How: re-extracted the organizers' docs from the new dashboard bundle into `docs/organizers/` (rules, problems, contract, quickstart, overview, challenge changed; the 73 published cases did not). `scripts/scored.py`: `status`, and `loop`, which fires a scored call the moment `eligibility.private_wait` reaches zero at the heaviest problem still owed passes, and dials practice cases in the gaps. `scripts/restart.sh` raises `logs/.hold` and waits for `logs/.run-in-flight` to clear, so a restart never lands on a call. `scripts/practice.py` got a `batch` command and rides out platform hiccups. Removed the test hook left in `speech.py`. Practice on the new problems before the first scored call: 6 of 6 passed.
Ref: 71b56d9

## 2026-09-19 · fix · submissions retry inside the 30-second window
By: Mark Skrypka
Why: in the second Run All the platform's submit endpoint timed out on 8 of 22 calls (its API was answering in 4–6 s instead of 0.2 s); we made one attempt each, and 3 cases failed.
How: `tools.finalize` retries a timed-out or 5xx/429 POST until 27 s after hang-up, treats 409 (identical repeat) as delivered, never retries a 4xx rejection, and sends several actions together in order; each attempt times out after 7 s. Two tests. Deployed 12:45 with the line idle.
Ref: f69cb71

## 2026-09-19 · fix · tool calls Gemini wrote as text cost two scored calls; four more causes of slow and wrong calls
By: Mark Skrypka
Why: the first Run All scored 36 of 40: both misses were calls where Gemini wrote its tool call as text ("cat=default_api:find_patient{…}"), the agent read that out, no lookup ran, the model copied itself every turn and the call died at the three-minute wall. Practice calls had shown four more faults: whole replies written twice (one call 185 s), replies into a caller's half-sentence, a wrap-up clock that replaced a correct offer with a fresh search, and a chart note that turned a booking into a reschedule.
How: `speech.py` — `GuardedGoogleLLM` releases text a sentence at a time, never speaks a sentence that is not speech, parses the written call (`tools.parse_leaked_calls`) and runs it as the real call, keeps it out of the context; `ReplayFilter` drops a replayed reply at character level; `PatientTurnStop` waits 2 s longer when the transcript has no closing punctuation (true of all 21 half-sentences in 240 logged turns). Greeting and holding phrase no longer enter the context twice. Nudge 7 → 10 s. Wrap-up at 140 s names the offer on the table and locks new searches until the caller speaks. Chart notes hidden by default; `reschedule` is questioned once when the caller never asked to move anything. `scripts/practice.py` rides out platform hiccups and has a `batch` command. Verified: 70 tests pass (4 live ones skip: their published slot is now in the past); a local call with every tool call forced through the recovery path booked correctly; on the harness "When Exactly" #5 (181 s fail → 115 s pass), "The Rules" #5 (185 s fail → 87 s pass) and a smoke call on the final build passed.
Ref: f69cb71

## 2026-09-19 · fix · registration reworked after a read-back loop ran a real call into the three-minute wall
By: Mark Skrypka
Why: on the harness the caller never accepts a spoken email read-back (it compares its own speech-to-text of our voice with the written address), so "Is that correct?" looped for 186 s and nothing was registered.
How: no email read-back; `repair_email` rebuilds the name part from the captured name; `check_national_id`; nine-digit phone check; three-question flow; wrap-up clock at 145 s; `scripts/restart.sh` never restarts during a call (one practice call was lost that way). Result: "The New Patient" 4/4 through the harness at 94–123 s; text evals 141/146 over two full runs; 53 tests pass.
Ref: f69cb71

## 2026-09-19 · fix · seven failure causes found by the evals and the first real practice calls
By: Mark Skrypka
Why: the first full eval run passed 61/73 and the first registration calls through the harness passed 1/4; each miss traced to one cause.
How: names compared in code (the directory API flags a shared surname as a name match); decisions recorded and POSTed at hang-up so a change of mind replaces instead of adding; hang-up fallback uses the last offer or refusal reason; `find_slots(after_appointment_id=…)`; no constraints the caller did not state; insurer guard and read-back rules for registration; recovery of tool calls the model wrote as text. Two regression tests added; 49 pass.
Ref: f69cb71

## 2026-09-19 · feat · evals without phoning, and the practice lane scripted
By: Mark Skrypka
Why: Mark asked for a way to know the agent works without calling it again and again; the jury scores exactly that.
How: `evals/run.py` plays each published case in text (caller = LLM on the case's own prompt; agent = production prompt, tools and model; clock pinned; submissions captured) and `evals/scoring.py` reproduces the leaderboard's match rule, tested against the organizers' normalization table. `scripts/practice.py` registers the tunnel, dials published cases through the real harness and prints verdict, lost fields and transcript.
Ref: f69cb71

## 2026-09-19 · feat · the call server: Pipecat pipeline on the Twilio-format wire, verified with local test calls
By: Mark Skrypka
Why: piece 1 of the plan — a talking agent on the wire — and the only way to prove the audio loop before the dashboard endpoint is ours to switch.
How: `prompt.py`, `bot.py`, `server.py`, `scripts/local_call.py`, `scripts/serve.sh`. Three local calls with a synthesized patient: greeting, identification by caller id + name, slot search, booking; captured submission equals today's accepted answer each time; no server errors. Replaced Pipecat's default end-of-turn model with a silence timeout after it fragmented a dictated DNI; added one holding phrase per turn after measuring ~6 s of lookup silence. Not yet run through the organizers' harness.
Ref: f69cb71

## 2026-09-19 · chore · voice vendors cut from three credentials to two keys
By: Mark Skrypka
Why: Mark asked for fewer services; Soniox plus a Google Cloud service-account JSON was more setup than the task needs.
How: Deepgram now does both speech directions (Nova-3 in, Aura-2 out) on one key, Gemini Flash stays as the decider; checked Deepgram's concurrency limits (150 STT / 45 streaming TTS on pay-as-you-go) and that Pipecat 1.11's Deepgram services import; swapped the empty names in `.env`, `.env.example`, `config.py`, `pyproject.toml`; decision and its Catalan trade-off recorded in `decisions.md`; contract and work plan updated. Tool layer untouched — 40 tests still pass.
Ref: f69cb71

## 2026-09-19 · feat · agent tool layer and clinic client, verified against published cases
By: Mark Skrypka
Why: the leaderboard scores only the submitted actions, so the rules the API does not apply for us had to exist in code — and be proven — before any voice work.
How: Python 3.13 venv + `pipecat-ai==1.11.0`; `src/clinic_agent/` with ids, dates, geo, clinic client, call session and nine tools; submissions accept only ids seen in the same call and never expose a patient's national id or phone to the model. Tests: 23 unit + 17 published cases through the live read-only API, all matching the accepted answers. Two API traps found and handled: leave is not reported as blocked; closure-day slots are still listed.
Ref: f69cb71

## 2026-09-19 · docs · organizers' docs captured; stack decided; contract v3
By: Mark Skrypka
Why: the organizers' docs define the task far more precisely than the public brief — the wire, the submissions, the scoring, the 18 problems — and they reverse our framework choice.
How: extracted the eight docs pages, API spec, 73 published cases and clinic catalogue into `docs/organizers/`; wrote `research/2026-09-19-harness-contract.md`; verified the team key and the dashboard login (both in git-ignored `.env`); recorded the stack (Python + Pipecat, Soniox → Gemini Flash → Google TTS, text evals, ngrok) in `decisions.md`; rewrote `contract.md` and `work.md`; added `.gitignore`.
Ref: f69cb71

## 2026-09-18 · docs · stack research landed; scope slimmed to "keep it simple"
By: Mark Skrypka
Why: the stack decision needed evidence, and the first recommendation came out production-grade; Mark cut it back to a simple agent that does exactly what the task expects, plus automated evals.
How: eight probe notes and a cross-check in `active/clinic-voice-agent/research/`; Mark's decisions recorded in `decisions.md`; `contract.md` rewritten as draft v2; `work.md` re-planned around the organizers' docs page; parked items listed as follow-ups.
Ref: f69cb71

## 2026-09-18 · docs · open initiative "Clinic voice agent" and capture the track brief
By: Mark Skrypka
Why: the Prosper track brief lived only in screenshots; every session, teammate and research probe needs the same source of truth.
How: transcribed the brief to `active/clinic-voice-agent/research/2026-09-18-track-brief.md`; drafted `contract.md`, `work.md`, `decisions.md`; launched Deep stack research.
Ref: f69cb71

## 2026-09-18 · chore · stem first run — planning docs and managed block
By: Mark Skrypka
Why: empty repo; the discipline needs a home before the first task.
How: created `docs/planning/` (README, worklog) and planted the stem managed block in a new `CLAUDE.md`.
Ref: f69cb71
