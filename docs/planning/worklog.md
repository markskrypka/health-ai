# Worklog

Newest first. One entry per change, written when the change lands.

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
