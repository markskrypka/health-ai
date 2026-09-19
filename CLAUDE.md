<!-- stem -->
Always work through the stem skill: size the work, keep
docs/planning/ current, verify before done.
Now: Clinic voice agent (HackSpain Prosper track) — 148 points, rank 1 at 19:30 on 19 Sep: all 14 open problems credited 4/4 (a scored run now dials four calls at once). scripts/scored.py loop runs in the assistant's session, idles until a problem opens and picks it up (logs/scored-loop.log); change code via scripts/restart.sh, which pauses it. Not open yet: nearest_site, the_questions, second_policy, the_real_call (60 points) — they decide the board. Leader's repo read: research/2026-09-19-competitor-cachopo.md. Mark's standing decisions: scored runs automated day and night, commit after each verified fix (no pushes), no full text-eval runs unasked, Deepgram not ElevenLabs for now, jury material after the open problems are banked. Deployed 20:20: a later move keeps doctor and clinic, "the next one" keeps the clinic, caller id always counts (text evals green; the published later move passed through the harness at 21:07). The tunnel dropped 20:54–21:04 on a network timeout — watch the connection. Next: the research note's order (safety nets keyed on an open offer, second_policy, a nearest_site step) — docs/planning/active/clinic-voice-agent/work.md. Wall freezes Sunday 20 Sep 06:00 Madrid.
<!-- /stem -->

## Admin web interface — a separate initiative, not started

Mark wants a live front-desk screen (patients on the left, the conversation with booking and cancellation artifacts in
the middle, the patient card on the right; monorepo, Next.js). Read `docs/planning/active/admin-web/brief.md` and ask
Mark its questions before writing any code. It must never touch the call server or the scored loop.
