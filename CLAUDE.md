<!-- stem -->
Always work through the stem skill: size the work, keep
docs/planning/ current, verify before done.
Now: Clinic voice agent (HackSpain Prosper track) — 172 points, the maximum, at 22:10 on 19 Sep: all 16 open scored problems credited 4/4 (tied with refugia2 and vortex). Not open yet: second_policy, the_real_call. scripts/scored.py loop runs in the assistant's session, idles until a problem opens and dials it (logs/scored-loop.log); change code via scripts/restart.sh, which pauses it. Mark's standing decisions: scored runs automated day and night, commit after each verified fix (no pushes), no full text-eval runs unasked, ElevenLabs for the voice only and picked by the team's ears (needs ELEVENLABS_API_KEY in .env), deep gap audit with a plan before fixes. Next: docs/planning/active/clinic-voice-agent/work.md. Wall freezes Sunday 20 Sep 06:00 Madrid; demos 11:00–13:00.
<!-- /stem -->

## Admin web interface — a separate initiative, not started

Mark wants a live front-desk screen (patients on the left, the conversation with booking and cancellation artifacts in
the middle, the patient card on the right; monorepo, Next.js). Read `docs/planning/active/admin-web/brief.md` and ask
Mark its questions before writing any code. It must never touch the call server or the scored loop.
