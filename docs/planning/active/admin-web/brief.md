# Brief — the admin web interface ("the front desk screen")

**Status:** not started. Mark runs this as its own session. **Ask him the questions below before writing any code.**

## What Mark asked for (his words, 19 Sep 2026)

> a web interface for the agent where an admin will be able to see all the patients in the left sidebar, and chat
> window in the center of the page, and the patient card at the right, and so all the info changes/updates realtime,
> the things like booking, etc is displayed in the chat as artifacts also realtime, cancelling bookings should also be
> visible in the chat, the realtime transcription should be displayed in the chat, etc.

His stated preferences: **a monorepo; Next.js for the admin.** He wants to be asked about the architecture and the
file layout, not handed one.

## What it is for

The jury on Sunday 20 Sep judges what the leaderboard ignores: "what you can see while it is happening, what you can
learn from it afterwards, and whether you can show any of it working." This screen is the visible half of that. It is
not scored by the leaderboard, so it must never put a scored call at risk.

## What exists to build on

- **The call server** — `src/clinic_agent/server.py`, port 7860, one Pipecat pipeline per call (`bot.py`). Do not add
  work to its hot path, and never restart it except with `scripts/restart.sh` (it pauses the scored loop and waits
  for the call in flight).
- **Per-call event logs** — `logs/calls/<call_id>.jsonl`, append-only, written live by `CallSession.log`
  (`src/clinic_agent/session.py`). Every line is `{"t": seconds since the call connected, "kind": …, …}`:

  | kind | fields | meaning |
  |---|---|---|
  | `call_started` | `has_caller_id` | the socket opened |
  | `caller` / `agent` | `text` | one finished turn (agent text can be empty when the turn was only a lookup) |
  | `tool_call` / `tool_result` | `name`, `args` / `result` | a lookup or a decision tool, and what the model was told |
  | `patient` | `patient_id`, `matched_on`, `status` | the patient was identified |
  | `offer` | `offers[]`, `notes[]` | slots offered (the first is the one spoken) |
  | `blocked` | `reason`, `blocked` | a clinic rule stopped the request |
  | `recorded` | `action`, `payload`, `replaced[]` | a decision (book, reschedule, cancel, register, no-action, escalate) and what it replaced |
  | `refusal_not_recorded`, `discarded` | … | a refusal dropped because another decision stands; decisions taken back |
  | `voice`, `listening_model` | `language` | the voice changed language; a Catalan caller moved the listening model |
  | `quiet_line`, `wrap_up_clock`, `inferred_at_hangup`, `recovered_leaked_call` | … | the safety nets firing |
  | `submit` | `action`, `payload`, `http`, `attempts` | the decision POSTed to the organizers at hang-up |
  | `call_ended` | `submissions`, `posted` | the call is over |

- **The read-only console** — `src/clinic_agent/console.py` + `console.html`, its own process on port 7870:
  `/api/calls`, `/api/calls/{id}?after=n`, `/api/numbers`. It polls; it is a working reference for reading the logs.
- **The clinic API** — read-only, `docs/organizers/clinic-api.md`, key in `.env` (`PROSPER_API_KEY`): `/directory`
  (a search, not a listing), `/patients/{id}/appointments`, `/availability`, `/clinic`. Python client:
  `src/clinic_agent/clinic.py`.

**What is not there yet:** a push stream of events (SSE or WebSocket); words as they are recognised (only finished
turns are logged); any way to list all ~2,900 patients (the public API searches; the organizers' dashboard has its own
listing behind a login); and the clinic is read-only, so a "cancellation" on this screen is the agent's CANCEL
decision being shown, not something the screen performs.

## Questions to ask Mark first

1. **Monorepo layout.** Where do the Python agent and the Next.js app live (`apps/agent`, `apps/admin`, `packages/…`)?
   Do we move the existing `src/` now, or only after the wall freezes (Sunday 06:00)? Moving files under a running
   scored loop is a risk with no points in it.
2. **Tooling.** Package manager and Node version (on 18 Sep he chose Node LTS + pnpm for an earlier plan), TypeScript
   settings, linting.
3. **Realtime transport.** SSE from a small Python service that tails the logs (no change to the call server), a
   WebSocket, or the Next.js server tailing the files itself?
4. **Watch or act?** Does the admin only watch, or also act (take a call over, drop a recorded decision before it is
   sent)? Acting means touching the call server.
5. **"All the patients."** Everyone in the clinic (needs a listing source) or the patients who have called? Search,
   sorting, what marks a patient as "on a call now"?
6. **Patient card.** Which fields; and are the national id and the phone shown in full, masked, or not at all? (The
   agent never lets the model see them.)
7. **Live transcription.** Finished turns (exists today) or words as they are recognised (a small logging addition in
   `bot.py`)? The agent's words as they are spoken?
8. **Artifacts.** Which moments become cards in the conversation: offer, booking, reschedule, cancellation,
   registration, refusal with its reason, escalation? Are replaced decisions shown struck through?
9. **Where it runs on Sunday.** His laptop only, or a URL the jury can open? If a URL: auth.
10. **Look.** A component library (shadcn/ui?), light or dark, English or Spanish UI.
11. **History.** Live calls only, or past calls too, and how far back?
12. **Proof.** What shows it works? A replay mode that streams a recorded call log at real speed is cheap and makes
    the demo independent of the harness.

## Constraints

Work through the stem skill. Commit after each verified step, never push (Mark's standing decisions). Secrets live
only in `.env`; never print or commit them. Read-only against `logs/`; nothing here may slow or restart the call
server while scored calls can still arrive (until Sunday 06:00). The jury session is Sunday.
