# Decisions — The jury demo

Newest first. Each with its why.

## 2026-09-20 03:30 · Mark's answers to the plan
- **A full monorepo, now:** `apps/agent` + `apps/web`. Mark: the changes on the voice agent are finished and merged to
  `main`, so the move no longer collides with them. How it is kept safe under the running phone server and scored loop
  is piece 0 in `work.md`.
- **Work on `main`, no worktree.** The worktree made at 00:50 was removed; nothing had been committed there.
- **The middle of the desk is a chat window, not a flow chart.** Mark: "there should be a chat window in the middle
  where we'll display the agent actions along with the transcript in realtime." The agent's actions are cards inside
  the conversation; the patient's photo sits on the identification card. React Flow is dropped.
- **Extras in:** word-by-word transcript with answer times; generated photos; live mood per turn. **Out:** tapping a
  slot on the calendar.
- **The jury uses the caller's screen on our laptop only.** No public address, no login, no phone layout.
- **Order:** the desk first, then the caller's screen, then what we learn.

## 2026-09-20 03:35 · Pipelines: A is the ElevenLabs voice, B the Deepgram voice
Since 03:12 the agent speaks with ElevenLabs when its key is set and with Deepgram without it — both paths exist in the
code. So the comparison is real from the first call: the registry picks the voice per call. This replaces the 00:50
decision below ("Pipeline B is a small, real difference").

## 2026-09-20 · The teammate's branch is not a base
`origin/feat/jury-defense-and-live-dashboard` is left alone — Mark, 00:35: "that was our other teammate trying different
things out. Forget it." Nothing is read from it or merged from it.

## 2026-09-20 · The log is the bus; the call server is not touched
The screens are fed by a separate process that tails `logs/calls/*.jsonl` and pushes new lines to the browsers.
Why: the phone line is still scoring until 06:00 and is judged by the jury after; the logs are already written the
moment things happen, so tailing costs well under a second; the same path serves the phone line, the browser calls and
replays; and a crash of the demo can never take a call down.
Not chosen: publishing events from inside the call server — it puts the demo on the call's event loop.

## 2026-09-20 · The browser dials in the harness's own wire format
The caller's page sends the same Twilio-format 8 kHz µ-law frames as `scripts/local_call.py`.
Why: browser calls run through exactly the pipeline the jury is judging, with no new transport and no new dependency
(WebRTC would need `aiortc`, which is not installed, and a second pipeline configuration). Cost: it sounds like a phone.
Parked as a follow-up: 16 kHz audio for browser calls.

## 2026-09-20 · Browser calls get their own call server, in dry run
Port 7861, started from this worktree with `DRY_RUN_SUBMIT=1`.
Why: the phone line's process is never restarted for the demo, and a browser call carries a call id the platform never
issued — its decisions are captured and shown, not POSTed.

## 2026-09-20 · What the screen adds is gated by the call itself
`screen`, the form's details and the pipeline choice arrive in the `start` message. A phone call never carries them, so
its prompt, its tool list and its behaviour stay byte-identical; a test holds that.
Why: the agent behind the demo must be the agent that scored — and the jury's phone call must not change because a
screen exists.

## 2026-09-20 · The form fills from what the agent acts on, not from every word
Fields fill from the arguments of `find_patient`, `check_national_id` and `register_patient`, then get a tick from the
record. Why: it is exact (it is what the agent really captured), needs no second model listening to the call, and lands
1–2 seconds after the caller speaks — fast enough to read as live.

## 2026-09-20 · Mood is measured after the call, by the events service
Why: it needs the whole conversation to mean anything, it must never sit on the call's path, and cached once per call it
costs next to nothing. Live mood per turn is a stretch, computed the same way, off the call.

## 2026-09-20 · Photos are generated, never real
The clinic API has no photo (the record carries `sex` and `date_of_birth`). Everyone gets an initials avatar; the
handful of published personas we demo with get a generated portrait, stored by patient id. The patients are the
organizers' fictional personas.

## 2026-09-20 · Pipeline B is a small, real difference
A is today's agent. B changes one model setting per call through `pipelines.py`. Why: the comparison table must hold
real calls under two pipelines by 11:00; ElevenLabs as a pipeline touches the voice router and belongs to Mark's
separate voice task — it can join the registry as C when that lands.
