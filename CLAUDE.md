<!-- stem -->
Always work through the stem skill: size the work, keep
docs/planning/ current, verify before done.
Now: Clinic voice agent (HackSpain Prosper track) — 96 points at 18:10 on 19 Sep (16 of 17 scored calls passed). scripts/scored.py loop runs in the assistant's session, owns both lanes and picks up problems as they open (logs/scored-loop.log); change code via scripts/restart.sh, which pauses it. Owed: languages, noise, no_slot_free, change_and_cancel; problems 15–18 not open yet. Language build deployed 17:58 (voice per language, Catalan listening model). Mark's standing decisions: scored runs automated day and night, commit after each verified fix (no pushes), no full text-eval runs unasked, Deepgram not ElevenLabs for now, jury material after the open problems are banked. Next: read failed scored calls from logs/calls/, then jury material — docs/planning/active/clinic-voice-agent/work.md. Wall freezes Sunday 20 Sep 06:00 Madrid.
<!-- /stem -->
