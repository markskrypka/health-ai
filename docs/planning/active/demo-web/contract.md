# Contract — The jury demo: the caller's screen and the front desk screen

**Status:** agreed by Mark, 20 Sep 2026 03:30 Madrid, with five changes to the draft (all in `decisions.md`): the repo
becomes a full monorepo now; the work happens on `main`, no worktree; the middle of the desk is a **chat window** — the
transcript with the agent's actions in it — not a flow chart; the extras that are in are word-by-word transcript with
answer times, generated photos and live mood per turn; the jury uses the caller's screen on our laptop only.
Replaces the initiative "Admin web interface" (never started): its brief is kept in `research/`.

## Goal

On Sunday 20 Sep, 11:00–13:00, the team has ten minutes in front of the jury. The jury scores what the leaderboard
ignores. This initiative builds what we show for three of their criteria (`docs/organizers/challenge.md`):

- **3 · The platform around the agent** — "how a call is actually run, what you can see while one is in flight, whether
  you can answer *why did it say that?* afterwards, and whether ten concurrent calls hold up. Surprise us."
- **6 · Engineering rigour** — "the failure modes you can name, and what a call costs you in money and seconds."
- **7 · The jury's discretion** — "something nobody asked for, an idea worth stealing."

Two screens, one agent. The agent behind both is the same pipeline that answers the phone line.

## What the jury sees

### The caller's screen (`/call`) — a patient on the clinic's web page

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ Clínica Arenal                                              ● On the call 00:42 │
├────────────────────────────────┬──────────────────────────────────────────────┤
│ YOUR DETAILS (optional)        │ FREE APPOINTMENTS                            │
│  Full name   Mercedes Váz… ✓   │ Traumatology · Dra. Peral · Arenal Norte     │
│  DNI / NIE   •••••716Y    ✓   │  Mon 21  Tue 22  Wed 23  Thu 24  Fri 25      │
│  Born        26/09/1946   ✓   │    –       –       –       –     10:45 ◀ said │
│  Phone       ••• ••• 529       │                                  11:00       │
│  Email                         │                                  11:15       │
│  Insurer     Mapfre       ✓   │ "Tell me the day and time that suits you."   │
│                                │                                              │
│     [  📞  Call the clinic  ]   │ YOUR APPOINTMENT                             │
│     ~~~ voice level ~~~        │ ✓ Fri 25 Sep · 10:45 · Dra. Nuria Peral ·    │
│                                │   Arenal Norte · Mapfre                      │
│ agent: "The earliest with Dra. │                                              │
│ Peral is Friday at 10:45…"     │                                              │
└────────────────────────────────┴──────────────────────────────────────────────┘
```

- **The form is optional.** Filled in before calling: the agent already knows who is ringing — it greets them by name
  and never asks who they are. Left empty: the fields fill themselves while the caller talks — first as the agent heard
  them, then with a tick once they match the clinic's record.
- **The calendar** shows the free slots of the agent's latest search. The agent says the first option, then invites the
  caller to look at the screen and say the day and time that suits them. The chosen slot turns green when it is booked.
- The call is a real call: microphone in the browser, the same 8 kHz phone pipeline, interruptions work.

### The front desk screen (`/desk`) — the admin

```
┌────────────────┬─────────────────────────────────────────────┬───────────────────┐
│ [Live 2] [Past]│ Call 090c… · 01:12 · EN · web · pipeline A  │ PATIENT           │
│                │                                             │ (photo)           │
│ ● Mercedes V.  │ caller  I need the earliest with Dr Peral.  │ Mercedes Vázquez  │
│   booking…     │                                             │ Ortega · 79 · F   │
│   01:12 EN 🙂  │      ┌ IDENTIFIED · name + phone ─────────┐ │ P00580            │
│                │      │ (photo) Mercedes Vázquez Ortega    │ │ DNI •••••716Y     │
│ ● Unknown      │      └────────────────────────────────────┘ │ Mapfre · seen     │
│   identifying… │      ┌ SEARCH · orthopaedics · Dra. Peral ┐ │ before            │
│   00:19 ES 😐  │      │ Norte · earliest · 112 ms          │ │ Referrals: derm., │
│                │      │ Fri 25 · [10:45] [11:00] [11:15]   │ │ orthopaedics      │
│                │      └────────────────────────────────────┘ │ Chart note: …     │
│                │  The earliest with Dra. Peral is Friday…    │ UPCOMING          │
│                │                         agent · 1.3 s 🙂    │  – …              │
│                │ caller  Yes, that works.                    │ THIS CALL         │
│                │      ┌ BOOKED ────────────────────────────┐ │  + Fri 25 · 10:45 │
│                │      │ Fri 25 Sep 10:45 · Peral · Norte   │ │                   │
│                │      └────────────────────────────────────┘ │                   │
│                │ caller  thank y…  (words as they arrive)    │                   │
└────────────────┴─────────────────────────────────────────────┴───────────────────┘
```

- **Left:** the calls in progress; a toggle shows past calls instead (206 real ones are already on disk).
- **Middle — a chat window.** The transcript in realtime, word by word, and between the turns the agent's actions as
  cards: identification (with the patient's photo on success), appointments checked, search, a clinic rule that bit,
  offer, booking, move, cancellation (a replaced decision is struck through), registration, refusal with its reason,
  escalation, safety nets, sent to the clinic. Each agent turn shows how many seconds it took to answer; each caller
  turn gets a mood mark about a second later.
- **Middle, past call:** the same chat, plus a header: the outcome and whether it was delivered, seconds and cost, the
  caller's mood across the call, and **which agent pipeline took the call** — with a table comparing pipelines, so
  agents can be A/B tested. Clicking a sentence of the agent shows the lookup result and the rule behind it: "why did
  it say that?".
- **Right:** the patient's card — who they are, plan, referrals, chart note, upcoming appointments, and what this call
  changed.

## What is realtime

| What | Realtime? | How far behind | What it needs |
|---|---|---|---|
| A call appearing and ending in the list | yes | < 1 s | nothing new — the log file appears |
| Finished turns of caller and agent | yes | at the end of the turn | nothing new |
| Lookups and their results, identification, offers, rules, decisions, replaced decisions, safety nets | yes | < 0.2 s | nothing new — all logged the moment they happen |
| Patient card and photo | yes | with the identification | nothing new for the basics; masked id, sex and chart note need the record in the event (new build) |
| The form filling itself | yes | 1–2 s after the caller says it — when the agent acts on it | nothing new on the agent |
| The calendar of free slots | yes | with the offer | one new event: the full list behind an offer (new build) |
| The slot turning "booked" | yes | instantly | nothing new |
| Words as they are recognised; the agent's words as spoken; seconds to answer per turn | yes | ~0.3 s | a passive observer on the call pipeline (new build) |
| Which pipeline took the call | yes | fixed at the start | a field at call start (new build); older calls get their build from git history |
| The caller's mood, turn by turn | yes | ~1 s after each caller turn | a small model call per caller turn, made by the events service, never by the call server |
| The call's full analysis (mood across the call, friction, summary, lesson) | **after the call** (2–4 s after hang-up) | — | one model call over the transcript, by the events service |
| Sent to the clinic | **at hang-up only**, by design | — | decisions are POSTed when the call ends, so a change of mind replaces a decision instead of adding one. Browser calls are dry runs: shown as "captured, not sent" |
| The clinic's own diary changing | **no** | — | the clinic API is read-only and static: a booked slot stays "free" there. The screens overlay this call's booking themselves |
| The admin listening to the audio live | **no** | — | needs an audio tap on the call pipeline — out |
| The harness's verdict on a call | **no** | — | published by the platform later — out |

"New build" means agent code written for this demo. Browser calls use it from the start, on their own call server. The
phone line (port 7860) keeps the build it is running until Mark decides otherwise after the 06:00 freeze. **The front
desk must be good on today's events alone; the new events add polish.**

## Scope

**In:** the move to a monorepo (`apps/agent`, `apps/web`); the two screens above; an events service (push stream over
the call logs, patient card data, mood per turn, post-call analysis, replay of a recorded call as if live); a second
call server for browser calls (port 7861, dry run); small, gated additions to the agent (form details known before the
greeting, a screen-aware prompt block, the new events, a pipeline registry: A the ElevenLabs voice, B the Deepgram
voice); generated patient photos; `scripts/demo.sh` and `docs/demo.md` (the ten-minute script and its fallbacks).

**Out:** acting on a call from the desk (taking over, dropping a decision); live audio monitoring; a listing of all
2,900 patients; login and public hosting; anything that writes to the clinic; call recordings; phone-sized layouts;
tapping a slot on the calendar; a flow chart.

**Stretch, only if the pieces are done:** an "Evidence" tab (eval runs, variance across repeats, cost per call).

## What must always be true

- Before the freeze (Sunday 06:00) this work never restarts the phone line's server and never stops the scored loop.
  The move to a monorepo leaves both running processes untouched, and `restart.sh` works from its new place the moment
  the move lands.
- A phone call behaves exactly as before: the screen and the form exist only when the browser's call says so. The phone
  prompt and tool list stay byte-identical — a test holds this.
- A replay is always labelled a replay. Browser calls are always labelled dry runs.
- Full national ids and phone numbers never reach a screen other than the caller's own form; the desk shows them masked.
- Secrets stay in `.env`. No pushes. Commit after each verified piece.

## Success criteria

1. A call on the phone line — or a replay of one — appears on the desk within a second; its chat, action cards and
   patient card build while it runs. Ten at once stay readable.
2. Any finished call opens with its chat, outcome, delivery, mood and pipeline; clicking an agent sentence shows the
   lookup result and the rule behind it.
3. From the caller's screen with an empty form, a spoken call fills the form, shows the search's free slots, and the
   chosen slot turns booked.
4. With the form filled in for a patient on file, the agent greets them by name and never asks who they are.
5. The pipeline table compares at least two pipelines with real calls under each.
6. The existing test suite passes from `apps/agent`; the phone prompt and tool list are byte-identical to what they
   were before this work.
7. `scripts/demo.sh` starts everything; `docs/demo.md` holds the script and the fallbacks.

## Spend

Browser test calls cost what a practice call costs (speech + Gemini, cents each). Mood per turn is one small model call
per caller turn; the full analysis is about 2,000 tokens per call — all 206 past calls together stay under one dollar,
and it runs only when a call is opened, or on a button. Photos: a few cents each, for the six or so people we demo
with. Nothing else is bought.

## Approvals

- Mark — scope and order: **agreed, 20 Sep 2026 03:30** ("Yes, go"), with the five changes named at the top.
