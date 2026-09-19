# Competitor read: cachopo (github.com/pablofd/hackspain), 19 Sep 18:35–19:45

**Question.** Is the leader's approach better than ours, why, and what should we take from it?
**Decision it informs.** Where tonight's hours go before problems 15–18 open and the wall freezes (Sun 06:00).
**Depth.** Deep: four parallel read-only probes (brain and write path · voice and turn-taking · deterministic
helpers · readiness for problems 15–18) plus my own reading of their README, their 500-line failure diary
(`AGENTS.md`) and their prompt; every claim about our side checked against our code, our 176 call logs or the
live read-only clinic API. Their repo was cloned to the session scratchpad, last commit 19 Sep 14:18; nothing of
theirs was copied into ours.

## Answer

No. Their lead at 18:30 (132 vs our 96) was calls banked, not a better agent. While this note was being written
our loop banked languages, noise, no_slot_free, change_and_cancel and the new "wild_card": **148 points, rank 1
at 19:30, every open problem 4/4**. Anyone who caps the open set ties at 148, so the board is decided by
problems 15–18 (60 points) and by the jury.

## What they built (verified by reading)

- TypeScript on Node 24; **one speech-to-speech model** (Azure OpenAI Realtime `gpt-realtime-1.5`, `whisper-1`
  transcripts, `semantic_vad`), no separate STT/TTS. An experimental GPT-Live connector sits beside it.
- A large guarded tool layer (`src/receptionist.ts`, 1,572 lines): `find_patient`, `resolve_request`,
  `search_availability` with a deterministic EN/ES/CA `date_phrase` parser, `prepare_action` →
  read-back → **a new caller turn must agree** → `confirm_action(s)` → immediate POST. An accepted action can
  never be replaced; nothing is ever submitted on hang-up.
- Request-scoped state (`request_id` per patient and intent), held plans per patient, a code gate on refusals
  (reason must come from the current `blocked` evidence; a coverage refusal is rejected until the second-plan
  question is answered), an emergency latch, CartoCiudad geocoding for nearest site.
- ~10,000 lines of offline tests on synthetic fixtures; no replay of the published cases; scored calls admitted
  by hand, one at a time. OpenTelemetry spans, private NDJSON call records, optional stereo WAV, a bearer token
  on `/ws`.

## Findings

1. **Our write path fits the scoring better — verified.** They POST mid-call and cannot undo; their diary records
   two mismatches from exactly that (a refusal sent before the caller accepted an alternative; a BOOK sent 0.7 s
   before "…but do you have anything outside working hours?") and a regex consent gate built to compensate. We
   record decisions, let the last one replace, POST at hang-up with retries, and fall back to the offer on the
   table. Their propose→confirm turn is also why **12 of 23 of their calls hit the 180 s wall, 7 with no record**;
   0 of our 18 measured scored calls ran past 150 s (median 90 s).
2. **Their voice layer is not more reliable — verified from their diary and our logs.** One run of theirs fell to
   3/40 on silent callers; one call died of output overflow; their only clock is the 180 s kill. Ours: fixed TTS
   greeting 0.8 s after connect, wrap-up clock at 140 s, nudge on a quiet line. Measured on 100 of our calls:
   caller stops → our first audio 2.45 s median (1.54 s after the end-of-turn decision); our audio ends → caller
   speaks 3.37 s median, tight spread. **3.9% of turns stall ≥ 8 s** (median cost 13.8 s) — the harness sometimes
   does not notice our turn ended; theirs died on that, our nudge rescues it.
3. **Where their code is stricter than ours and it can flip a record:**
   - a later move **keeps the original doctor and site in code** (`later_search`); ours only sets the lower time
     bound and trusts the model to restate doctor and site — *verified; and our reschedule path has never run
     live: all four change_and_cancel scored calls were cancels*;
   - each slot is bound to the patient it was searched for; ours lets any identified patient take any slot —
     *verified, matters for two-patient calls (the_real_call, weight 5)*;
   - a refusal's reason is checked against the search's evidence, and a coverage refusal waits for the
     second-plan question; ours is advice in a tool result — *verified, matters for second_policy (weight 4)*;
   - nothing can be recorded after an ESCALATE; ours lets a later book replace it — *verified, low odds*;
   - a one-letter slip on a short surname ("Dr. Sanz" for Sáez) asks for confirmation; ours returns
     provider_not_found, which also becomes the hang-up default — *verified offline*;
   - named doctor + weekday + site where she does not sit that weekday: theirs relaxes to her earliest slot
     there, which is the published accepted answer; ours anchors on the first such weekday and rolls forward —
     *strong: a day-level simulation puts ours later in 37 of 49 doctor/site/weekday combinations; the one
     published case happens to coincide*;
   - phone: they strip +34 and require nine digits, we keep the last nine; email: they validate the shape, we
     do not convert "at/arroba", "dot/punto" — *verified*.
4. **Where ours is ahead — verified:** replaceable decisions and the hang-up fallback; one search that rolls
   forward to the soonest matching slot (theirs needs permission and a second round trip); caller id as an
   identifying detail (saves a turn on most calls); a Catalan listening model and a voice per language (theirs:
   one prompt line); email and check-letter repair; text evals over the 73 published cases with the board's own
   match rule, and an automated scored loop. Same on both sides: one earliest offer not a menu, name + one
   identifier, ids and phones never shown to the model, one second-plan question, privado never a fallback.
5. **Readiness for 15–18 (60 points) is where we are exposed — our text evals gave false comfort:**
   - the_real_call (5): in 2 of 3 published cases the first intent is a RESCHEDULE "next time, same doctor, same
     site, nothing earlier" for a relative, then a BOOK for the caller with a corrected weekday. Our move guard
     does not recognise "cannot make his appointment" / "no va a poder ir" and answers "book instead"; doctor and
     site are not pinned; once one action is recorded the wrap-up clock, the quiet-line nudge and the hang-up
     fallback all switch off, so a cut call posts one action of two; the prompt says goodbye after the first
     action. Estimated ~175 s live before any noise — *verified in code and by an offline run; never run live*.
   - second_policy (4): one published caller cannot recall the plan's name until asked to check the card; our
     prompt says "if they name one… otherwise end"; nothing checks the caller actually said the plan we bill —
     *strong*.
   - nearest_site (3): in 8 of 12 text-eval runs the model named the closest site from its own knowledge and
     passed `location_id`, so our geocoder never ran; "Calle de Preciados 3" returned address_not_found; no live
     call has ever used `caller_address`. Theirs resolves the address with a tool before anything else —
     *verified from eval-runs; theirs likelier to pass as things stand*.
   - the_questions (3): even. Ours has the catalogue in the prompt per doctor; site-centric questions ("is there
     a GP at Sur on Fridays?") need the model to invert it — *inferred*.
6. **From our own live calls during this read (not from their repo):**
   - A scored languages call failed to identify "Alice Collins Davies", heard as "Alys Davis", although her NIE
     was sound and on file and she rang from her own number: the lookup that carried the NIE no longer carried
     the caller id. Confirmed against the live directory. **Fixed and deployed 19:35** (caller id is always
     evidence; a sound id forgives a mangled name; 3 regression tests). The harness redialled her and she passed.
   - The one no_slot_free miss: "That time doesn't work, what's the next one?" — we offered the next time across
     all doctors (09:15 Ortiz, Centro) instead of the next with the offered doctor and site (09:15 Sáez, Sur
     existed). The answer is hidden until Monday; *inferred* that "next" keeps doctor and site. In both such
     calls the model also misused `after_appointment_id` with a slot ref before searching again.
   - A scored run now dials **four calls at once**; `scripts/scored.py` logs only the first case's verdict.
   - Platform GETs have no retry (10 s timeout); a timeout costs a spoken apology and a repeated lookup. Their
     diary shows 11 platform timeouts in one 23-call batch this morning.

## Recommendation (in order; nothing here touches banked points — credited passes cannot be lost)

1. the_real_call: recognise a move from `after_appointment_id` and the missing phrases; pin doctor and site from
   the appointment; key the clock, nudge and hang-up fallback on "an offer is open" rather than "nothing
   recorded"; no goodbye after the first of two actions. Then one practice call on a published the_real_call case.
2. second_policy: "cannot name the plan → ask them to check the card and wait"; bill only a plan the caller said.
3. nearest_site: a `nearest_site(address)` step before identification that stores the ranked order; `find_slots`
   uses it and ignores a model-supplied site; geocoder fallbacks (full address → street + town → town).
4. "The next one": later offers keep the first offer's doctor and site; the tool result tells the model to offer
   the next in the list instead of searching again.
5. Small, safe: bind slots to their patient; emergency latch; edit-distance-1 doctor names return "confirm";
   phone/email normalisation; one in-code retry on platform GETs; log every case of a scored run.
6. the_questions: a generated "by site" facts block with explicit negatives.

**Do not copy:** immutable mid-call writes, the confirm-in-a-new-turn flow and its regex consent gate,
`confirm_actions`/`get_call_state`, permission-gated next-day search, the +9 dB gain, the model-spoken greeting,
speech-to-speech itself (no time, and their diary shows it is the source of their lost calls).
**Optional, unproven:** a bounded 4 s silence tail after our speech (~35 lines in `bot.py`); try only with six
practice calls measuring the 3.9% stall rate, revert if it does not move.
**For the jury:** their failure diary and their privacy notes are strong "what you learned" material — our
worklog is the same thing; a bearer token on `/ws` is a ten-minute answer to "boundaries".

## Gaps

Their score history per problem is not public, so "banked earlier" is inferred from the board and their commit
times. Private expected answers are hidden until Mon 21 Sep 00:00, so finding 6b is a reading, not a fact. The
three `tts_error` signals on passed calls were not investigated.
