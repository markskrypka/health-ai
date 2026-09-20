"""The leaderboard's pass rule, reproduced: a case passes when the submitted action list equals one of
the accepted lists after the organizers' published normalization (docs/organizers/normalization-table.md).

Ids are compared exactly. Tolerance exists only where a voice was in the loop: registration fields
and the slot. Binary — no partial credit.
"""

import json
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

MADRID = ZoneInfo("Europe/Madrid")
_VERBS = {"book": "BOOK", "reschedule": "RESCHEDULE", "cancel": "CANCEL", "register": "REGISTER",
          "no-action": "NO_ACTION", "escalate": "ESCALATE"}
_REGISTER_FIELDS = ["given_name", "first_surname", "second_surname", "national_id", "date_of_birth",
                    "phone", "email", "insurer"]


def fold(text: str) -> str:
    """NFKD, combining marks stripped, case folded — also turns ñ into n, as the scorer does."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).strip().casefold()


def norm_slot(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(MADRID).replace(second=0, microsecond=0).isoformat()


def norm_phone(value: str) -> str:
    return re.sub(r"\D", "", str(value))[-9:]


def norm_national_id(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", str(value)).upper()


def to_record(submission: dict) -> dict:
    """Our captured submission ({'action': 'book', ...payload}) in the shape the platform records it."""
    verb = _VERBS[submission["action"]]
    fields = {k: v for k, v in submission.items() if k != "action"}
    if verb == "REGISTER":
        return {"action": verb, "new_patient": {k: fields[k] for k in _REGISTER_FIELDS if k in fields}}
    return {"action": verb, **fields}


def canonical(action: dict) -> dict:
    out: dict = {"action": action["action"]}
    for key, value in action.items():
        if key == "action":
            continue
        if key == "slot":
            out[key] = norm_slot(value)
        elif key in ("policy_id", "appointment_type_id", "reason"):
            out[key] = fold(value)
        elif key == "new_patient":
            p = value
            out[key] = {
                "given_name": fold(p["given_name"]),
                "surnames": sorted([fold(p["first_surname"]), fold(p["second_surname"])]),  # order is free
                "national_id": norm_national_id(p["national_id"]),
                "date_of_birth": str(p["date_of_birth"]),
                "phone": norm_phone(p["phone"]),
                "email": re.sub(r"\s", "", str(p["email"])).casefold(),
                "insurer": fold(p["insurer"]),
            }
        else:
            out[key] = value  # ids: exact
    return out


def _key(actions: list[dict]) -> list[str]:
    return sorted(json.dumps(canonical(a), sort_keys=True, ensure_ascii=False) for a in actions)


def passes(submissions: list[dict], acceptable: list[dict]) -> bool:
    ours = _key([to_record(s) for s in submissions])
    return any(ours == _key(option["actions"]) for option in acceptable)


def diff(submissions: list[dict], acceptable: list[dict]) -> list[str]:
    """Field-level differences against the closest accepted answer — for debugging, never for scoring."""
    ours = [canonical(to_record(s)) for s in submissions]
    best: list[str] | None = None
    for option in acceptable:
        want = [canonical(a) for a in option["actions"]]
        lines: list[str] = []
        if [a["action"] for a in ours] != [a["action"] for a in want]:
            lines.append(f'actions: submitted {[a["action"] for a in ours]}, accepted {[a["action"] for a in want]}')
        for mine, theirs in zip(ours, want):
            for field in sorted(set(mine) | set(theirs)):
                if mine.get(field) != theirs.get(field):
                    lines.append(f'{theirs["action"]}.{field}: submitted {mine.get(field)!r}, accepted {theirs.get(field)!r}')
        if best is None or len(lines) < len(best):
            best = lines
    return best or []
