# The jury demo — how to start it, what to show, what to do when something fails

Demos: Sunday 20 Sep 2026, 11:00–13:00, ten minutes per team. The jury scores what the leaderboard ignores
(`docs/organizers/challenge.md`): the call itself, how personal it gets, **the platform around the agent**, safety,
language, **engineering rigour**, and one mark at their discretion.

## Start

```bash
apps/agent/scripts/demo.sh          # dry-run call server 7861 · events service 7870 · web app 3100 — Ctrl-C stops all three
```

Then open **http://localhost:3100/desk** on the projector and **http://localhost:3100/call** in a second window.
Use **Chrome** and a **headset** — on speakers the agent can hear itself and interrupt itself.

The phone line is separate and is not started by `demo.sh`: the server on 7860 and the tunnel (`apps/agent/scripts/night.sh`,
or `restart.sh` for the server alone). `demo.sh` prints whether 7860 answers.

| What | Where | Log |
|---|---|---|
| Phone line — the jury's call, the harness | 7860, through the tunnel | `logs/server.log`, `logs/calls/` |
| Dry-run call server — calls from the caller's screen | 7861 | `logs/demo-server-7861.log`, `logs/calls/` |
| Events service — feeds both screens from `logs/calls/` | 7870 | `logs/events-service.log` |
| Web app | 3100 | `logs/web-dev.log` |

## Ten minutes

1. **The jury rings (3 min).** The desk is on the projector before the phone rings. The call appears in *Live* the
   second it connects; the chat fills turn by turn; each lookup is a card — who was found, what was searched, which
   rule bit, what was offered, what was decided, what a change of mind replaced. The patient's card fills on
   identification (id and phone masked). Say once: *nothing here touches the call — the agent writes its log, a
   separate process reads it.*
2. **Why did it say that? (1 min).** Open the call in *Past*. Click a sentence of the agent: the lookups behind it light
   up, with the words the tool gave the model. Point at the strip above: seconds, seconds to a decision, how fast it
   answers, what the call cost, which pipeline took it, the caller's mood and the one lesson a model read out of it.
3. **The caller's screen (3 min) — the part nobody asked for.** On `/call`, press *Call the clinic* with the form empty
   and ask for an appointment. Give a name and a date of birth: the form fills itself and gets its ticks; the calendar
   fills with every free time of the agent's search; the agent says one and tells you the rest are on your screen. Say
   a day and a time you can see — it is offered; say yes — it turns green. Then the second call: fill the form in
   first (a published persona: **Josefa Domínguez Navarro**, DNI **48064716Y**) — *"good morning, Josefa"*, and nobody
   asks who she is. Same agent, same pipeline as the phone line; the page dials it in the harness's own wire format.
4. **Ten at once (1 min).** *Replay ten at once* on the desk: ten recorded calls run side by side at their real speed.
   They are labelled replays. (Real concurrency is the harness's Switchboard burst on the phone line.)
5. **How we know it works (2 min).** *Compare pipelines*: every call says in its first log line which agent took it —
   A speaks with ElevenLabs, B with Deepgram — and the same measures stand side by side. Then the numbers that are not on
   a screen: 127 agent tests, a text-eval runner over the 73 published cases with repeats (`apps/agent/evals/`), a
   reducer test that builds every one of the 200-odd real call logs, and the audit of the night in
   `docs/planning/active/clinic-voice-agent/`.

## When something fails

| What you see | What to do |
|---|---|
| Desk says *events service not reachable* | `demo.sh` is not running, or 7870 died: start `demo.sh` again. The calls themselves are unaffected. |
| The room's network is gone | The desk still works on everything already on disk: open *Past*, *Replay as if live*. Replays need no network. |
| *Call the clinic* shows an error in red | It says why. Microphone refused → allow it in the address bar and reload. *Could not reach the call server* → 7861 is down: `demo.sh`. |
| The agent interrupts itself on a web call | Speakers: put the headset on. |
| The agent is silent on a web call | ElevenLabs may be out of quota: pick voice **B · Deepgram** under the call button and call again. |
| A web call booked nothing although you hung up on an offer | By design: on the web page a hang-up is not a yes. (The phone line guesses at hang-up because the harness fails silence.) |
| Portraits missing | Only the eight patients who rang most have one (`apps/agent/scripts/portraits.py`); everyone else shows initials. |

## What is real and what is not

- Calls from the caller's screen are **dry runs**: the decision is captured and shown, never POSTed — the page says so.
- The clinic API is read-only and static: a booked slot stays "free" there. The screens overlay the call's own booking.
- Moods and lessons are a model's reading of the call's log, made after each caller turn and once at the end, beside the
  call and never on it. On the phone line most callers are the organizers' simulated personas.
- Cost per call is an estimate at list prices (`PRICES` in `clinic_agent/console.py`) from what the call logged.
- The live words, answer times, pipeline badge, slot list and masked card come from agent code newer than the build the
  phone line runs. Until the phone line is restarted on it (Mark's decision, after the freeze), phone calls show
  everything else: turns, lookups, identification, offers, rules, decisions, delivery.
