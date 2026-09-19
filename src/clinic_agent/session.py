"""Everything one call owns. One CallSession per socket — nothing here is ever shared."""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import config


@dataclass
class CallSession:
    call_id: str
    from_number: str | None = None
    # "Now" for this call: the moment it connected, in Europe/Madrid. Evals pin it to the case.
    now: datetime = field(default_factory=lambda: datetime.now(config.MADRID))
    # Evals and local test calls capture submissions instead of POSTing them.
    dry_run: bool = False
    # Text evals keep their events in memory only.
    persist_log: bool = True

    # Only ids that tool results produced in THIS call may be submitted.
    patients: dict[str, dict] = field(default_factory=dict)
    slots: dict[str, dict] = field(default_factory=dict)
    appointments: dict[str, dict] = field(default_factory=dict)
    last_offered_slot: str | None = None
    last_offered_patient: str | None = None
    # The reason the last search gave for not offering anything (blocked rule, no availability…).
    last_refusal_reason: str | None = None
    # Who and what the latest search was for: (patient_id, specialty_id). A refusal is about that request.
    last_search: tuple[str, str] | None = None
    # Whose chart the caller id opened, when that is not the patient being booked for.
    caller_record: dict | None = None

    # What the caller said and what the agent said, turn by turn. Lets code check that a value was said
    # rather than invented, and recover a tool call the model wrote out as text instead of making.
    heard: list[str] = field(default_factory=list)
    said: list[str] = field(default_factory=list)
    insurer_challenged: bool = False
    # The language the agent is speaking right now ("en" or "es") — it picks the voice and the stock phrases —
    # and whether the caller turned out to speak Catalan, which needs its own listening model.
    language: str = "en"
    catalan: bool = False
    move_challenged: bool = False
    # A search for "later than the appointment I hold" is itself the caller asking to move it.
    move_intended: bool = False
    # Set when the wrap-up clock fires with an offer on the table, cleared by the caller's next turn:
    # the clock alone must never make the model search again and book something the caller never heard.
    search_locked: bool = False

    # Decisions recorded during the call. They are POSTed when the call ends (the window stays open
    # 30 s after the socket closes), so a caller who changes their mind replaces a decision instead
    # of adding a second, contradictory action that can never be withdrawn.
    submissions: list[dict] = field(default_factory=list)
    posted: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    _t0: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        """Seconds since the call connected. Calls are cut off at 180."""
        return time.monotonic() - self._t0

    def log(self, kind: str, **data: Any) -> None:
        """Append-only event log: the answer to 'why did it say that?'."""
        event = {"t": round(time.monotonic() - self._t0, 3), "kind": kind, **data}
        self.events.append(event)
        if not self.persist_log:
            return
        config.CALL_LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.CALL_LOG_DIR / f"{self.call_id}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def remember_slot(self, slot: dict) -> str:
        ref = f"S{len(self.slots) + 1}"
        self.slots[ref] = slot
        return ref
