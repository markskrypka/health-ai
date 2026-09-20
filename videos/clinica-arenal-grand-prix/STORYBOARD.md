---
format: 1920x1080
duration: 180s
message: "Clínica Arenal turns one healthcare call into a safe, explainable, scalable care workflow"
arc: "Stakes → Patient Experience → Desk Mission Control → Explainability → Post-Call Intelligence → Multi-Pipeline Architecture → Concurrency → Rigour"
audience: "Grand Prix judges in San Francisco evaluating creativity, problem-solving, and craftsmanship"
mode: autonomous
music: ambient cinematic
---

# Clínica Arenal — Grand Prix Film Storyboard

## Video direction

A three-minute judge-facing film demonstrating creativity, problem-solving, and craftsmanship.
The visual style uses the Blue Professional design preset re-themed with Clínica Arenal's deep medical teal (`#0f6b5c`), warm background (`#ffffff` / `#f6f4ef`), dark ink (`#1c1a17`), and crisp Geist typography.
Every frame balances high-definition real UI captures from the live web application with animated vector accents, data telemetry, and explainability callouts.

---

## Frame 1 — The Healthcare Bottleneck

- status: animated
- src: compositions/frames/01-hook.html
- duration: 22.5s
- transition_in: cut
- scene: Dark cinematic clinical opener with voice waveform and healthcare stakes
- voiceover: "Every morning, healthcare clinics face an impossible choice: rushed conversations, endless hold times, or missed patient care. Clínica Arenal is not another generic conversational bot. It is a real-time, explainable clinical voice operating system engineered to handle live patient phone calls with precision, safety, and warmth."
- asset_candidates:
  - capture/extracted/tokens.json

### Narrative

Scene 1 opens on an elegant, dark-to-light hospital corridor motif with an active audio waveform visualization pulsing in teal. Large editorial typography introduces the core problem of clinic phone congestion, transitioning into the bold brand reveal: "Clínica Arenal · Clinical Voice Operating System".

---

## Frame 2 — The Dual-Surface Caller Experience

- status: animated
- src: compositions/frames/02-patient-screen.html
- duration: 22.0s
- transition_in: crossfade
- scene: Real patient browser phone at /call with live auto-filling identity form and calendar
- voiceover: "We designed what we call the dual-surface experience: the caller's screen. A patient can ring directly from any phone line or web browser. As Josefa speaks naturally, the interface extracts structured clinical data, auto-filling her identity and rendering open physician slots directly on her screen in real time."
- asset_candidates:
  - capture/screens/06-caller-screen-initial.png
  - capture/screens/07-caller-screen-prefilled.png

### Narrative

Camera pans into the browser phone interface at `/call`. Visualizes the dual-surface concept: while the patient speaks naturally, speech recognition parses her name ("Josefa Domínguez Navarro") and National ID, lighting up green checkmarks on the form in real time. Beside it, the clinic appointment calendar populates with Dr. Rafael Ortiz's available morning slots.

---

## Frame 3 — Front-Desk Mission Control

- status: animated
- src: compositions/frames/03-desk-overview.html
- duration: 21.0s
- transition_in: crossfade
- scene: High-resolution live desk console at /desk with active call queue and HIPAA-grade masking
- voiceover: "On the other side of the line is the Front-Desk Mission Control. Receptionists and clinic administrators do not just see a transcript. They see live identity verification against clinic records with strict HIPAA-grade masking, ensuring national IDs and telephone numbers are safeguarded by design."
- asset_candidates:
  - capture/screens/01-desk-overview.png
  - capture/screens/02-call-detail-cards.png

### Narrative

Smooth glide across the live reception desk at `/desk`. Shows the real-time call queue, latency badges, and patient identification card. Emphasizes clinical data privacy: patient IDs and phone numbers are masked (`•••••716Y`, `••••••0529`) while still confirming insurance coverage with Sanitas.

---

## Frame 4 — Total Explainability & Clinic Rules

- status: animated
- src: compositions/frames/04-explainability.html
- duration: 21.5s
- transition_in: crossfade
- scene: Action cards illuminating deterministic database lookups and booking rules
- voiceover: "In healthcare, black-box AI is unacceptable. We built complete explainability into every turn. Clicking any agent response reveals the exact tool call and clinic rule behind it: insurance eligibility verified, referral constraints checked, and doctor offers validated before the patient hears a single word."
- asset_candidates:
  - capture/screens/02-call-detail-cards.png
  - capture/screens/03-booking-decision.png

### Narrative

Macro focus on the conversational action cards. Demonstrates explainability: clicking the agent's turn illuminates the precise tool execution (`find_slots`, `book`), the raw arguments, and the verified clinic rule constraint. Shows the booking confirmation locked with doctor, time, and location.

---

## Frame 5 — Real-Time Sentiment & Lessons

- status: animated
- src: compositions/frames/05-insights.html
- duration: 19.0s
- transition_in: crossfade
- scene: Post-call analytics strip showing mood arc, friction detection, and operational lessons
- voiceover: "Every completed call is analyzed by a companion model. It charts the caller's emotional trajectory across each turn, flags conversational friction points, estimates call cost down to fractions of a cent, and delivers actionable operational lessons for clinic staff."
- asset_candidates:
  - capture/screens/03-booking-decision.png
  - capture/screens/01-desk-overview.png

### Narrative

Examines the analytical telemetry bar above the chat. Displays the caller sentiment score (Mood index 1.4 → 2.0), low-effort rating, friction flags (e.g. caller paused while considering time slot), estimated API cost ($0.038), and an automated clinical takeaway lesson generated by the companion analysis model.

---

## Frame 6 — Multi-Pipeline Resilience

- status: animated
- src: compositions/frames/06-pipelines.html
- duration: 21.0s
- transition_in: crossfade
- scene: Pipeline comparison modal contrasting ElevenLabs Flash and Deepgram Aura-2 fallback
- voiceover: "Clinical reliability demands architectural redundancy. Arenal supports hot-swappable multimodal voice pipelines. Pipeline A delivers warm, expressive speech via ElevenLabs Flash, while Pipeline B provides an instant fallback via Deepgram Aura. If a vendor stutters, the patient never notices."
- asset_candidates:
  - capture/screens/04-pipeline-comparison.png

### Narrative

Opens the "Compare pipelines" modal overlay. Displays architectural comparison: Pipeline A (Warm Voice: Deepgram Nova-3 + Gemini 2.5 Flash + ElevenLabs Flash) versus Pipeline B (Fast Fallback: Deepgram Nova-3 + Gemini 2.5 Flash + Deepgram Aura-2). Shows round-trip response metrics, token counts, and cost differences.

---

## Frame 7 — Concurrency at Scale

- status: animated
- src: compositions/frames/07-concurrency.html
- duration: 20.0s
- transition_in: crossfade
- scene: Ten concurrent patient calls replaying simultaneously on the live desk
- voiceover: "Under peak morning load, the system does not queue patients into silence. Here, ten concurrent calls are replayed side by side at full production speed. The event-driven architecture handles simultaneous calendar bookings, locks, and state reductions without a single race condition."
- asset_candidates:
  - capture/screens/05-replay-ten-concurrency.png

### Narrative

Demonstrates heavy-load concurrency. Triggering "Replay ten at once" activates ten simultaneous live call streams on the desk. Visualizes the event-driven architecture, SQLite diary lock guarantees, and state reducers updating all ten conversations in real time.

---

## Frame 8 — Engineering Rigour & Grand Prix

- status: animated
- src: compositions/frames/08-rigour-outro.html
- duration: 23.0s
- transition_in: crossfade
- scene: Metric counters (127 tests, 73 benchmark evals, 200+ call logs) and Grand Prix closing
- voiceover: "Behind the interface lies uncompromising engineering: one hundred and twenty-seven agent tests, seventy-three benchmark evaluations with repeated trials, and code-enforced safety gates that immediately route emergencies. Clínica Arenal: crafted for clinicians, built for patients, and engineered for the Grand Prix."
- asset_candidates:
  - capture/extracted/tokens.json

### Narrative

Stat counters roll up to 127 Unit & Integration Tests, 73 Benchmark Evals, 100% Deterministic Safety Gates, and Trilingual Fluency (English, Spanish, Catalan). Concludes with the Clínica Arenal emblem and Grand Prix San Francisco presentation banner.
