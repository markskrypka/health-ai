# Worklog

Newest first. One entry per change, written when the change lands.

## 2026-09-20 · fix · the demo build checked for the phone line: an independent review, four small guards, phone-mode calls on it
By: Mark Skrypka
Why: after the freeze Mark decides whether the phone line moves to the demo's build, and the jury judges that call. The question had to be answered with evidence: can anything added tonight change or endanger a phone call?
How: a read-only reviewer went through every change to `bot.py`, `tools.py`, `speech.py`, `session.py`, the new `screen.py`, `observe.py`, `pipelines.py` and Pipecat's observer code. Verdict: safe to restart, no blocker; for a phone call the prompt, tools, greeting, voice, tool results and `finalize` are the same, and what is added is log output and two passive observers (measured: ten calls at once go from 15.6% to about 19% of one core, loop lag unchanged). Its one material point — phone mode had never run on the new build — is closed: one phone-mode call on the dry-run server (source phone, pipeline A, the usual greeting, the accepted booking, no `at_time`, no word of a screen, 85 s) and three at once (all three booked the accepted slot, no server errors). Its four small guards are in: only a dry-run server takes `screen=1` (`bot.web_call`), the form's lookup cannot kill a call when the directory does not answer, a failing calendar log still leaves the offer, `restart.sh` unsets a stray `PIPELINE`. Found while Mark made his first spoken call from the browser (277 s, 26 turns, a registration — the microphone path works with a human voice): a turn with no words in it is no longer shown or read for mood, and in development a saved file no longer hangs up a live call (Fast Refresh runs every cleanup). 130 agent tests, 127 web tests.
Ref: 14a0af3

## 2026-09-20 · feat · what we learn from a call; portraits; one command to start the demo; the runbook
By: Mark Skrypka
Why: pieces 5–7 of "The jury demo": the jury asks what we can learn from a call afterwards and how we know the agent works; Mark asked for mood, the pipeline that took the call so agents can be A/B tested, a photo on identification, and live mood per turn.
How: `clinic_agent/analysis.py` reads calls beside the line, never on it — the caller's mood about a second after each of their turns, and every finished call once (mood across it and by turn, friction, effort, a summary, one lesson), kept in `logs/analysis/`; replays reuse the kept reading and cost nothing. The events service adds the reading (`/api/calls/{id}/analysis`), a batch (`POST /api/analysis`), cost per call from what it logged (`PRICES`, an estimate at list prices) and `/api/pipelines`; the desk shows a strip on a finished call (outcome, delivery, notes, seconds, seconds to decision, answer time, cost, pipeline, the reading) and "Compare pipelines". `scripts/portraits.py` generated faces for the eight patients who rang most, from the record's sex and age (the personas are invented; so are the faces); everyone else keeps initials. `scripts/demo.sh` starts the dry-run call server, the events service and the web app; `docs/demo.md` is the ten-minute script and what to do when something fails. A web call with no decision reads "hung up before deciding", not as a failure. Verified in a browser: a filled form greeted "good morning, Josefa" with every field ticked at second zero; on the desk the same call showed the form's lookup before the greeting, the portrait, a mood mark on the caller's turn and its reading; the comparison holds A (4 calls), B (1) and 212 earlier calls, 34 of them read. Spend so far tonight: seven short test calls, 35 readings, 8 images — about one dollar.
Ref: 0b31452

## 2026-09-20 · feat · the caller's screen: a phone in the browser, a form that fills itself, a calendar of the free times
By: Mark Skrypka
Why: pieces 3 and 4 of "The jury demo" — the part nobody asked for. A patient on the clinic's web page calls from the browser; what they typed is known before the greeting, what they say fills the form, and the free times the agent finds appear on a calendar, so the agent says one and lets them choose with their eyes.
How: the page dials a second call server (port 7861, `DRY_RUN_SUBMIT=1`) in the harness's own wire format (`apps/web/lib/phone`, built by a helper agent: microphone → 8 kHz µ-law frames, playback, `clear` on interruption; a recorded caller can stand in for the microphone, `?clip=`). What the page adds travels in the `start` message and lives in `clinic_agent/screen.py`: `screen=1`, the form as `prefill`, a pipeline choice. A filled form is looked up in code through `find_patient` before the greeting (logged as a lookup made by the form), the greeting uses the first name, and the prompt gets a block — identified, or typed but not on file, plus the calendar. Only such a call's `find_slots` takes `at_time`, and its result points the caller at their screen; a web caller who hangs up on an offer has not booked it (the harness's hang-up guess is left to phone calls). Additive, for every call: `call_started` carries source and pipeline (`pipelines.py`: A ElevenLabs, B Deepgram, per call), `patient` a card with id and phone masked, `availability` every free slot behind an offer; `observe.py` watches from beside the pipeline and logs the caller's words as recognised, the agent's words, seconds to answer, and what the call used. A phone call's prompt, greeting and tool list are what they were — `tests/test_screen.py` holds it. Verified: 127 agent tests (11 new), 126 web tests; a scripted web call with the form filled in was greeted "good morning, Josefa" and never asked who she was (41 s); from a real browser, a recorded caller was identified by name and date of birth, the form ticked itself, 250 free slots appeared with the offered one marked, and the agent said "the other free times are visible on your screen". The phone line (:7860) was not restarted; it still runs the build of 03:14.
Ref: 1f3210b

## 2026-09-20 · feat · the front desk screen, on the events the agent already writes
By: Mark Skrypka
Why: the jury scores "what you can see while a call is in flight" and "why did it say that?" afterwards; piece 2 of "The jury demo". It had to work on the phone line as it runs today, with no change to the agent.
How: `apps/web` (Next.js 16, Tailwind 4). `lib/events.ts` is one reducer — a call's event log in, what a screen shows out: the turns, the agent's actions as cards (identification with the patient on it, appointments on the books, nearest clinic, search with its offers, a clinic rule, decisions with what they replaced struck through, refusals by the code with their reason, safety nets, sent to the clinic), the patient's card, the form's fields, the booked slot. Every sentence of the agent carries the actions since its last one, so clicking it answers "why did it say that?" with the tool's own words to the model. `lib/desk-store.ts` follows the events service's stream and joins a call half-way without a gap. `/desk`: calls in progress or past calls on the left, the chat in the middle, the patient on the right with upcoming appointments read from the clinic; "Replay as if live" and "Replay ten at once". Verified: 15 reducer tests, one of which builds every call log on this machine (206) and checks each lookup got its card and each ended call its end; in a browser a replayed booking built list, chat and card in step, ten replays at once stayed readable, and a past move showed its why-panel. National ids and phone numbers are masked on the desk.
Ref: 84cff76

## 2026-09-20 · feat · the log becomes a stream; a recorded call can be replayed as if live
By: Mark Skrypka
Why: piece 1 of "The jury demo": the screens need every event the moment it is written, from the phone line too, without touching the server that takes the calls.
How: `clinic_agent/tail.py` follows `logs/calls/` and hands out every complete new line once, with its position in its log; `console.py` became the events service (port 7870): `/api/stream` (server-sent events: a snapshot of recent calls, then each new event and a fresh summary line per call), `/api/replay` (a recorded call re-emitted in memory with its original timing, its first event marked `source: replay`), the patient's upcoming appointments and the catalogue's names; summaries now carry who the call is about, its language, its source, its stage and whether it was a dry run. The old console page and its endpoints still work. Verified: five tests for the follower (history is not news, a late file, a half-written line, positions agree with a full read around a damaged line); a replay at 14x arrived over the stream in order with its stages.
Ref: 01afe19

## 2026-09-20 · refactor · the repo becomes a monorepo: the agent moves to apps/agent
By: Mark Skrypka
Why: the jury demo adds a web app (`apps/web`), and Mark chose a full monorepo now rather than after the demo — the voice-agent changes are finished and merged to `main`, so the move collides with nothing.
How: `git mv` of `src/ tests/ evals/ scripts/ pyproject.toml` into `apps/agent/`. `config.ROOT` and `practice.ROOT` still mean the repo root, so `.env`, `.venv/`, `logs/` and `docs/` stay where they were; the three shell scripts `cd` to the repo root and `night.sh` calls the scripts by their new paths; `pip install --no-deps -e apps/agent` re-pointed the editable install and touched no other package. Done under the running phone server and scored loop without disturbing them: both hold their modules and absolute paths in memory, and the package imports nothing lazily. Verified: 111 tests pass and 4 skip from `apps/agent`; a dry-run server started on 7861 from the new layout (root, keys, log folder and catalogue all resolve); the shell scripts parse; the phone line's `/health` answered before and after; the loop still runs. `restart.sh` was not run. The unstarted initiative "Admin web interface" is folded into "The jury demo" (`active/demo-web/`), its brief kept under `research/`.
Ref: 67f0434

## 2026-09-20 · feat · the agent speaks with ElevenLabs
By: Mark Skrypka
Why: the team found the Deepgram voices robotic and the Spanish one Latin American; Mark put `ELEVENLABS_API_KEY` in `.env` and asked for a plain switch now rather than more work on Deepgram.
How: `speech.voice_service`: with the key set, Pipecat's `ElevenLabsTTSService` — one voice for English and Spanish (`ELEVENLABS_VOICE_ID` — Mark's `.env` selects "Elise", the code's default is "Sarah"; `ELEVENLABS_MODEL`, default `eleven_flash_v2_5`), 8 kHz PCM straight to the line; without the key, Deepgram Aura-2 as before. The voice is not told the language: that is part of its connection, and the first cut reconnected at the change to Spanish and ElevenLabs took 2.1 s to close the old socket, right before the first Spanish sentence. `VoiceRouter` still tracks the language for the stock phrases. Verified: 111 tests; scripted local calls in English (the accepted booking, 68 s) and Spanish (every sentence came back as Spanish on the wire), no reconnects, no server errors, first audio byte median 0.13 s (max 0.39 s) over 13 sentences; deployed 03:12 with the line idle. Not known: the plan behind the key (it lacks `user_read`), so neither its character quota nor its concurrent-stream limit; if the voice goes silent, take the key out of `.env` and run `scripts/restart.sh`. One practice call through the real harness on this voice passed (simple_booking, 77 s, no signals). Elise is verified for Latin American Spanish, not Castilian; no voice the key can see is Castilian.
Ref: e27a31d

## 2026-09-20 · fix · "one more thing" discards nothing; an "okay" over a reply nobody heard is not an answer
By: Mark Skrypka
Why: a text eval of "The Real Call" failed once in six: after the grandson's move was recorded the caller said "Wait, don't hang up yet! I also need an appointment for myself" and the model called `discard_recorded` — the move was gone. And from the audit: 23 of 138 live decisions were recorded on an offer or a question the caller had talked over (Pipecat puts a sentence into the context when it is synthesised, not when it is heard), one of them a cancellation.
How: `tools.discard_recorded` runs only when the caller's last words take the decision back (English and Spanish), one challenge, then trust; its description and the prompt say a second request is a second action. `speech.SpokenClock` sits after the line's output and counts the seconds of the current reply really played; a reply interrupted with under 80% played (16 characters a second) is marked for the model ("[LINE] the caller did not hear your last reply") and `book`, `reschedule` and `cancel` refuse once while it stands (`tools._not_heard`); a hang-up clears it so the fallback still sends something. Verified: 3 new tests; the_real_call 12/12 over four runs; on a local call the scripted caller talked over the offer, the agent said it again and booked the accepted slot.
Ref: 6310c64

## 2026-09-20 · fix · the second plan, a family on one line, a time repeated back wrongly, a move whose doctor is blocked
By: Mark Skrypka
Why: audit findings on the two problems still unopened. second_policy: "I have something through work, not sure what it is called" ended the call, passing the plan on file switched off the question that finds the second one, and nothing checked that a billed plan was ever said; the organizers' control case (the first plan works) fails if the second is billed. the_real_call: the caller's number plus two shared surnames identified the grandson as the grandmother in 10 of 14 eval runs; a caller who repeated 14:00 back as "fourteen thirty" got a correct booking moved to 15:30 (live, 64300d72); a later move whose doctor cannot take the patient called `find_slots` for ever (stopped after 60 availability calls, offline).
How: `find_slots` drops an insurer equal to the one on file, answers a plan nobody said with `insurer_not_heard` once, and its blocked text and the prompt say: ask, and if they cannot name it ask them to read the card and wait; `_policy` bills the plan on file whenever it can pay. `find_patient`: through the caller id the given name must agree, or two exact details; several matches are narrowed by given name. `_offer` notes when its first slot is the one already recorded for that patient ("misheard, not changed their mind: say it again, change nothing"), and the prompt says the same. The blocked-doctor retry is a loop, not a recursion. Verified: 7 new tests, 108 in all; text evals second_policy 8/8, the_real_call 5/6 (the miss is the entry above).
Ref: 0c35fae

## 2026-09-20 · fix · the caller is not listened to while a lookup runs, nor as the answer begins
By: Mark Skrypka
Why: audit: "One moment, please." drew an "Okay" or "Sure, I'll wait" 78 times in 340; 38 cut the agent's reply off, 22 threw the model's run away, 18 cancelled the lookup itself (all 23 lookups that never returned were cancellations), about six seconds lost each — and twice a booking on a slot the caller had refused.
How: `speech.LookupMute`, a subclass of Pipecat's `FunctionCallUserMuteStrategy`: deaf from the start of a lookup until one second into the agent's answer, and never for more than six seconds after the last lookup returned. Verified: a unit test with a pinned clock; a local call booked the accepted slot.
Ref: 052b395

## 2026-09-20 · fix · what a refusal, an emergency and a withdrawal may undo; more red flags; no patient id in the tool schema
By: Mark Skrypka
Why: audit (privacy and safety): an off-topic refusal after a booking deleted the booking; an emergency could be followed by a booking or discarded; `discard_recorded` then a hang-up sent the booking the caller had withdrawn; the agent once said it was "escalating to emergency services" (nothing alerts anyone); a wish to die, an overdose, anaphylaxis and bleeding in pregnancy were not red flags; a published patient's DNI sat in the `find_patient` schema as an example and was spoken once to another caller.
How: `tools._record`: a refusal displaces a booking only with the very reason the last search gave for that patient and doctor; nothing is recorded after an ESCALATE; `discard_recorded` pops only the last decision, never an emergency, and withdraws the offer; `escalate` tells the model to say "call 112" and never to claim anyone was alerted; the red flags are broader and end with "anything that sounds life-threatening: escalate first"; the example id is gone, and a test keeps patient ids out of everything the model reads. Verified: 101 tests.
Ref: 724ea65

## 2026-09-20 · fix · an offer stands only until a later search or a nearest-clinic answer replaces it, and only for its patient
By: Mark Skrypka
Why: audit (scheduling): `last_offered_slot` changed only when a search returned, and `book` took any slot ref. Live, twice: the caller refused an offer, their next words cancelled the new search, and the refused slot was booked (ea105d64 after a nearest-clinic answer, e9096923 at the wrap-up clock). Offline: a relative's appointment could be moved onto the caller's slot and billed to the caller's plan.
How: `session.offer_round`, bumped by `withdraw_offer()` whenever a search goes out and when `nearest_site` names another clinic; every slot carries its round and the patient it was found for; `book` and `reschedule` answer `stale_offer` or `slot_of_another_patient`; an appointment anchor of another patient is refused. Verified: regression tests for both live calls' shape.
Ref: e17981d

## 2026-09-20 · fix · the call limit is ten minutes now
By: Mark Skrypka
Why: audit: `docs/organizers/rules.md` now caps a call at ten minutes (it was three), and our wrap-up clock still fired at 140 s. Since noon it had fired in four live conversations — three hurt, none helped: twice it made the agent say "call back" and record NO_ACTION while the caller was still spelling a name.
How: `config.WRAP_UP_AT_SECS = 540`; the two registration gates use it; the prompt's three-minute pressure is gone ("never rush a caller who is spelling… there is time"). Verified: the suite.
Ref: b65662b

## 2026-09-19 · fix · a question about the clinic gets only what was asked
By: Mark Skrypka
Why: the first scored run of "The Questions" passed 3 of 4. In the fourth the agent answered "Mondays and Wednesdays, from four to eight in the afternoon" to "which days is she there?" — the days were right, the caller's judge took the hours for a mistake and hung up; the same answer passed in another call of that run.
How: one prompt rule — answer only what was asked, in one short sentence, nothing added, then wait for the next question. An 18-question quiz of the deployed prompt and model (the five published questions plus thirteen variants) was 18 of 18 correct before and after, and carried no extras after. Deployed 22:05 inside the cooldown; the re-run passed 4 of 4: 172 points, every open problem credited 4/4.
Ref: b0e49f3

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
