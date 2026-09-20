<!-- stem -->
Always work through the stem skill: size the work, keep
docs/planning/ current, verify before done.
Now: Clinic voice agent (HackSpain Prosper track) — 172 points, the maximum (four teams tied); all 16 open scored problems credited 4/4. Live since 03:12 on 20 Sep: the gap audit's Tier 1 and the ElevenLabs voice (one voice for English and Spanish — .env selects "Elise"; ELEVENLABS_VOICE_ID swaps it; without ELEVENLABS_API_KEY the agent speaks with Deepgram). Next: the team keeps or swaps the voice after hearing its Spanish; then the audit's Tier 2 if Mark wants it before the demo — docs/planning/active/clinic-voice-agent/work.md lists what is left. scripts/scored.py loop and the ngrok tunnel run in the assistant's session (Mark: scripts/night.sh in your own terminal); change code only via scripts/restart.sh. Standing decisions: commit after each verified fix (no pushes), no full text-eval runs unasked. Wall freezes Sunday 20 Sep 06:00 Madrid; demos 11:00–13:00.
<!-- /stem -->

## Admin web interface — a separate initiative, not started

Mark wants a live front-desk screen (patients on the left, the conversation with booking and cancellation artifacts in
the middle, the patient card on the right; monorepo, Next.js). Read `docs/planning/active/admin-web/brief.md` and ask
Mark its questions before writing any code. It must never touch the call server or the scored loop.
