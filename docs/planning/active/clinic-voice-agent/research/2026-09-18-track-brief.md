# Track brief — HackSpain 2026, Prosper track (source of truth for requirements)

Source: `hackspain.app/tracks/prosper-ai`, transcribed from Mark's screenshots on 2026-09-18.
Status: verified (verbatim transcription). The starter kit and sign-up instructions are NOT captured yet — see Gaps.

## What you are building

A **voice AI agent that answers inbound scheduling calls for a clinic**, the way a receptionist would.

Someone rings. Your agent picks up, works out who is calling and what they need, looks them up in the clinic's records, finds real availability, and books, moves or cancels the appointment. Some calls should not end in a booking at all — the clinic cannot do it, the caller needs a doctor now, the rules say no — and recognizing those is as much a part of the job as booking well.

The voice model is one component of a system you design, not the system. The teams that do well build around it: real lookups, real availability, checks before anything is written, state that survives a caller changing their mind, and enough visibility to explain why the agent said what it said.

## How the weekend runs

Friday 18 → Sunday 20 September (2026).

1. **Register your team**, get your key, and stand up an endpoint we can call. The starter kit gets you a talking agent in minutes; everything after that is yours.
2. **Build and rehearse.** You can dial yourself as often as you like against published practice cases, answers included.
3. **Run for score** when you think you are ready. We call your agent with every problem, check what it did, and your points go on the leaderboard.
4. **Checkpoints.** Twice over the weekend the board freezes and prizes go to whoever is leading. Being early pays.
5. **Sunday: the final boss.** The jury calls your agent themselves, and you show them what you built.

## What the callers throw at you

**Eighteen problems**, each with its own person who rings you up. Each one isolates a single thing that makes a real front desk hard, sitting on top of the same ordinary booking:

- The simple booking, and ten of them at once.
- A caller the records do not know yet, and a caller who matches four people.
- Someone asking for a specific doctor, a specific site, or "the soonest."
- Vague times — "next Thursday", "first thing Monday" — that have to resolve.
- Requests the clinic's rules forbid, which must be refused for the right reason.
- A full diary with nothing free.
- Changes and cancellations.
- A parent calling for a child, a daughter for her father.
- Someone who should be sent to a doctor, not a calendar.
- Callers not speaking English, including other languages of Spain.
- A terrible line, a caller who interrupts and corrects and changes their mind, and someone trying to talk your agent into something it should not do.

## How you are scored

Two things, added together.

**The leaderboard — automatic, and brutally literal.** After each call your agent tells us what it did. Either that matches what the case accepts, or the case fails. There is no partial credit, no points for a nice conversation, and no credit for nearly. A call that correctly refuses still has to say so; silence is always wrong.

**The jury's final boss — everything the leaderboard ignores.** They call you themselves and judge the call as a person on the phone would: how it sounds, how it handles being interrupted, whether it feels like the clinic knows who is calling. Then they judge what you built around it — how a call is orchestrated, what you can see while it is happening, what you can learn from it afterwards, and whether you can show any of it working. Safety, language, and how you know your own agent works all count.

## Other verified facts

- Event: HackSpain 2026, UPM–ETSIT Madrid, in person, 36 hours, 18–20 Sept 2026. Max 15 teams per track (from the official site repo `HackSpain/hackspain26`, `apps/app/convex/tracks.ts`).
- Sponsor: Prosper AI (getprosper.ai) — voice AI for US clinic operations (scheduling, insurance verification, billing); $30M Series A led by a16z (June 2026).
- Infrastructure sponsors: Convex, Vercel, QuiverAI, Cloudflare, Tinybird, Cognition, Exa, fal.ai, Cursor, Helmcode. Perks per sponsor: not found publicly (`hackspain perk` in the CLI may list them).

## Gaps (blocking the final stack decision)

- **The harness contract is unknown**: what "an endpoint we can call" is (phone number, SIP URI, WebSocket, HTTP/WebRTC), what the "key" unlocks (clinic records API? a voice model?), how "your agent tells us what it did" is delivered (API call, schema), whether the scenario supplies a simulated "today" date, and where the harness is hosted (latency). Only the starter kit answers these — not publicly findable as of 2026-09-18.
- Checkpoint times are unknown.
