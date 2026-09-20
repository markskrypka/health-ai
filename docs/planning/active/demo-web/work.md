# Work — The jury demo: the caller's screen and the front desk screen

**State (2026-09-20, 03:40 Madrid) — agreed, building piece 0.** Mark's go came at 03:30 with five changes (see
`contract.md`, top). Work happens on `main` in the one checkout; the worktree made at 00:50 is gone. The phone line
(:7860, restarted 03:14 by the voice-agent work) and the scored loop keep running from this same checkout — the move to
a monorepo must not disturb them, and does not (see piece 0). Demos start at 11:00: seven hours.
**Next action:** piece 0 "A room to build in" — the monorepo move, then the web app's scaffold.
**Waiting on Mark:** one spoken test call from his browser when piece 3 lands (about 07:30).

## How it fits together

```
Browser — Next.js app, port 3100
  /call  ── WebSocket, the harness's own wire format (8 kHz µ-law) ──►  demo call server :7861
  /call  ◄── push stream (its own call only) ──┐                         same agent code, DRY_RUN_SUBMIT=1
  /desk  ◄── push stream (every call) ─────────┤
                                               │
                         events service :7870 ─┘  reads, never writes:   logs/calls/*.jsonl
                                                   ← the phone line :7860 (not restarted by this work before 06:00)
                                                   ← the demo call server :7861
```

- **The log is the bus.** Every call already writes an append-only event log the moment things happen. The events
  service tails the files and pushes each new line to the browsers (server-sent events). So the phone line needs no
  change to be watched live, both servers look the same to the screens, and a replay is the same code path.
- **One reducer.** `apps/web/lib/events.ts` turns a list of events into what a screen shows (chat items and action
  cards, form fields, calendar, patient card). Live and past calls, desk and caller page all use it. It is tested
  against real logs.
- **The browser dials like the harness does.** The page speaks the same Twilio-format frames as
  `scripts/local_call.py`, so browser calls run through the identical pipeline — no new audio transport, no new
  dependency. It sounds like a phone because it is one.
- **What the browser adds to a call** travels in the `start` message, next to `from_number`: `screen=1`, the form's
  details, a pipeline choice. A phone call never carries them, so it never changes.

## Where the files go

```
apps/agent/                       the Python agent, moved whole: pyproject.toml, src/clinic_agent/, tests/, evals/, scripts/
  src/clinic_agent/console.py     grows into the events service: stream, patient, mood, analysis, replay
  src/clinic_agent/analysis.py    mood per turn; the full analysis of a finished call, cached on disk
  src/clinic_agent/pipelines.py   the registry of agent pipelines (A = ElevenLabs voice, B = Deepgram voice)
  src/clinic_agent/observe.py     passive observer: words as recognised, sentences as spoken, seconds to answer, usage
  scripts/demo.sh                 starts the demo call server, the events service and the web app
apps/web/                         Next.js (App Router, TypeScript, Tailwind, shadcn/ui), pnpm
  app/call/                       the caller's screen
  app/desk/                       the front desk screen
  lib/events.ts                   event types and the reducer          lib/events.test.ts
  lib/phone/                      microphone → 8 kHz µ-law frames, playback, "clear" on interruption
  public/patients/                generated photos, by patient id
docs/ · logs/ · .env · .venv/     stay at the repo root (`config.ROOT` still means the repo root; a virtualenv cannot
                                  be moved under a running server — it moves to apps/agent after the demo, if at all)
docs/demo.md                      the ten-minute script, how to start, what to do when something fails
```

## New events (additive — old logs and the build on the phone line simply lack them)

| event | fields | who writes it |
|---|---|---|
| `call_started` | + `source` (phone · web · replay), `screen`, `prefilled` (field names only), `pipeline` {id, label, stt, llm, tts, prompt hash, build} | `bot.py` |
| `patient` | + `card` {names, date of birth, sex, insurer, seen before, referrals, chart note, id and phone **masked**} | `tools.find_patient` |
| `availability` | the search in words, and every free slot behind the offer (at most 300) | `tools._offer` |
| `hearing` · `speaking` · `latency` · `usage` | words as recognised · a sentence going to the voice · seconds from caller's last word to agent's first · tokens, characters, seconds at the end | `observe.py` |

Written by the events service, beside the logs, never into them: `logs/analysis/<call_id>.json` (mood per turn while
the call runs, the full analysis after it).

## Plan

Each piece ends with a commit. Times are Madrid.

0. **"A room to build in"** (03:40–04:20) — `git mv` of `src/ tests/ evals/ scripts/ pyproject.toml` into `apps/agent/`;
   `config.ROOT` and `practice.ROOT` point at the repo root again; the three shell scripts `cd` to the repo root;
   `pip install --no-deps -e apps/agent` re-points the editable install without touching any other package. Why this
   is safe under the running server and loop: both hold their modules and their absolute paths in memory, neither
   imports lazily from the package, and `logs/`, `.env`, `.venv/` do not move. Then `apps/web` scaffolded on port 3100,
   root `package.json` + `pnpm-workspace.yaml`, `apps/agent/scripts/demo.sh`. Done: the tests pass from `apps/agent`;
   a dry-run server starts on 7861 from the new layout; `restart.sh` parses and finds its paths (not run); the phone
   line's `/health` still answers; the web app answers on 3100.
1. **"The log becomes a stream"** (04:20–05:00) — `console.py`: `GET /api/stream` (snapshot of recent calls, then every
   new event of every call; `?call_id=` for one); `POST /api/replay` re-emits a recorded call as a new live one at real
   speed, labelled a replay. The console's old endpoints keep working. Done: `curl -N` shows a replayed call arriving
   with its original timing. Verify: unit tests for the tailer (a line written half-way, a file that appears).
2. **"The front desk on today's events"** (05:00–06:30) — the reducer with tests on real logs; three panes; Live/Past
   toggle; the chat window with action cards; patient card from `find_patient`'s result plus upcoming appointments
   fetched by the events service; initials avatar. Done: a replay builds list, chat and card in step; any past call
   opens; ten replays at once stay readable. Verify: reducer tests; screenshots through Playwright.
   **Checkpoint A, 06:30 — the desk is showable, including on the jury's own phone call.**
3. **"A phone in the browser"** (06:30–07:45; the audio module is built alongside piece 2 — disjoint files) —
   `lib/phone`; demo call server on 7861 (`DRY_RUN_SUBMIT=1`); `server.py`/`bot.py` read `screen`, `prefill`,
   `pipeline` from the `start` message; `/call` with the call button, timer and voice level. A hidden test mode plays a
   synthesized caller into the socket instead of the microphone, so the whole browser path is verified without a human.
   Done: a call from the page books an appointment and shows live on the desk. **Needs Mark once: one spoken call.**
4. **"The screen that listens"** (07:45–09:15) — form details known before the greeting: `find_patient` runs in code,
   the greeting uses the name, the prompt gets an ALREADY IDENTIFIED block (or ALREADY TYPED for someone not on file);
   the screen-aware prompt block and an exact `time` for `find_slots` — both only on screen calls; `availability` and
   `patient.card` events; the form filling from `find_patient` / `check_national_id` / `register_patient` arguments,
   ticked by the record; the calendar; the booked slot. Done: success criteria 3 and 4. Verify: unit tests for the
   prefill path and the gating; the byte-identical test for the phone prompt and tool list; two real calls.
   **Checkpoint B, 09:15 — both screens showable.**
5. **"What we learn, during and after"** (09:15–10:15) — `analysis.py`: mood per caller turn while the call runs, the
   full analysis after it (mood −2…+2 across the call, friction moments, caller effort, a one-line summary, one lesson;
   cached); `pipelines.py` with A and B chosen per call; old calls get their build from git history by time; past-call
   header and the pipeline comparison table (calls, seconds, seconds to decision, mood, flags, cost). Done: success
   criteria 2 and 5.
6. **"Alive while it runs"** (10:15–10:40) — `observe.py`: word-by-word transcript, seconds to answer per turn, usage
   and cost; "why did it say that?" links from a sentence to its cards. Photos for the people we demo with.
7. **"Ready for the room"** (10:40–11:00, and between other teams' demos) — `docs/demo.md`; a full rehearsal with Mark.

**Pre-decided cuts.** More than 30 minutes behind at checkpoint A: the comparison table and the photos go (initials
stay). Behind at checkpoint B: piece 5 shrinks to the mood marks and the pipeline badge; piece 6 to answer times only.

## Decisions still to come

- **After the 06:00 freeze — does the phone line move to the demo's build?** Gain: the jury's own phone call shows word
  by word, with the calendar list and the pipeline badge. Risk: the jury judges that call. If yes:
  `apps/agent/scripts/restart.sh`, one practice call through the harness, and straight back to the previous commit if
  anything looks different. If no: the desk still shows that call with everything today's events carry. Mark decides,
  not before piece 4 is verified.

## Follow-ups

Parked — not in the plan unless Mark pulls one in: the "Evidence" tab (eval runs, variance, cost); tapping a slot on the
calendar; a public URL for the jury's own phones; higher-fidelity audio for browser calls (16 kHz); call recordings with
a synced transcript; acting on a call from the desk; `.venv` moved into `apps/agent`.
