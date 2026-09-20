---
workflow: product-launch-video
flow: automation
storyboard: no
message: "Clínica Arenal turns one healthcare call into a safe, explainable, scalable care workflow"
destination: judge-screen
aspect: 1920x1080
language: en
audience: "Grand Prix judges in San Francisco evaluating creativity, problem-solving, and craftsmanship"
length: 180s
angle: "One call becomes a care operating system"
---

## Intent

A three-minute judge-facing film that sells and shows the product through one human call. Begin with the friction and stakes of getting care by phone, follow the call across the patient and front-desk experiences, then pull back to reveal the engineering that makes the experience safe, explainable, multilingual, and reliable under load. The tone is assured, humane, and cinematic rather than corporate.

## Assets

- `apps/web` — the real Next.js patient-call and front-desk experiences on upstream `main`.
- `apps/web/public/patients/` — synthetic patient portraits used by the live interface.
- `logs/calls/` — real call-event evidence when present; the interface also ships replayable demo material.
- `docs/demo.md` — the existing jury runbook and verified product claims.

## Customizations

- Feature the product's own captured screens as the proof layer: browser phone, live desk, explainable action cards, post-call insight, pipeline comparison, and ten-call replay.
- Use a professional English voiceover, a restrained music bed, precise UI sound cues, and styled captions.
- Use HyperFrames motion graphics to connect voice, structured events, safety rules, and outcomes into one visual system.
- Keep statistics source-traceable to repository evidence. Never invent performance or accuracy claims.

## Notes

- Delivery is a three-minute MP4 for an 11:00 judging session.
- Show patient information as synthetic and masked.
- Design for a large 16:9 judging-room screen and make key text readable without relying on captions.
- The user asked for the best possible result and explicitly suggested web-demo footage, TTS, and HyperFrames, so this run proceeds autonomously through the production build and stops at the required final preview before the high-quality render.
