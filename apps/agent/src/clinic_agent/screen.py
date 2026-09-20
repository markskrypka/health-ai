"""What a call from the clinic's web page adds to a phone call — and only to such a call.

The page dials in the harness's own wire format and says what it is in the `start` message, next to `from_number`:
`screen=1` and, as JSON in `prefill`, the details the caller typed into its form before ringing. A phone call
carries neither, so nothing in this module ever runs for one: its prompt, its tools and its greeting are exactly
what they were (tests/test_screen.py holds that).

What the page gets for it: a caller who filled the form in is recognised before the greeting and never asked who
they are; and the caller sees on a calendar the free times the agent finds, so the agent says one and lets them
choose the rest with their eyes.
"""

import json
from dataclasses import dataclass, field

from . import tools
from .clinic import ClinicClient
from .session import CallSession

FIELDS = ("name", "national_id", "date_of_birth", "phone", "email", "insurer")
_WORDS = {"name": "full name", "national_id": "DNI or NIE", "date_of_birth": "date of birth", "phone": "phone number",
          "email": "email address", "insurer": "insurer"}

# Only a web call's find_slots takes an exact time: the caller reads it off the calendar in front of them.
_TIME = {"at_time": {"type": "string", "description": "HH:MM, 24-hour. Only when the caller names an exact time they can see "
                                                   "on their screen; pass date_iso or weekday with it."}}


@dataclass
class Screen:
    typed: dict[str, str] = field(default_factory=dict)  # what the caller put into the form, by field


def from_start(body: dict) -> Screen | None:
    """The web page's part of the `start` message, or None: this is a phone call."""
    if str(body.get("screen") or "") != "1":
        return None
    try:
        raw = json.loads(body.get("prefill") or "{}")
    except ValueError:
        raw = {}
    typed = {k: str(raw[k]).strip() for k in FIELDS if isinstance(raw, dict) and str(raw.get(k) or "").strip()}
    return Screen(typed=typed)


async def identify(session: CallSession, api: ClinicClient, screen: Screen) -> dict | None:
    """Look the caller up from their form before the greeting, the way the model would — through find_patient, with
    its checks, and into the log as a lookup made by the form."""
    args = {k: screen.typed[k] for k in ("name", "national_id", "date_of_birth", "phone") if k in screen.typed}
    if not args:
        return None
    session.log("tool_call", name="find_patient", args=args, by="form")
    result = await tools.find_patient(session, api, **args)
    session.log("tool_result", name="find_patient", result=result, by="form")
    return result


def properties(tool: str, props: dict) -> dict:
    return {**props, **_TIME} if tool == "find_slots" else props


def greeting(usual: str, known: dict | None) -> str:
    """Recognition instead of interrogation: someone the records matched is greeted by their first name."""
    if not known or known.get("status") != "identified":
        return usual
    first = str(known.get("full_name") or "").split(" ")[0]
    return usual.replace("good morning.", f"good morning, {first}.", 1) if first else usual


def prompt_block(screen: Screen, known: dict | None) -> str:
    lines = ["THE CALLER'S SCREEN",
             "This caller is ringing from the clinic's web page, not from a phone, and is looking at that page while you talk."]
    typed = ", ".join(f"{_WORDS[k]}: {v}" for k, v in screen.typed.items())
    status = (known or {}).get("status")
    if status == "identified":
        facts = [f'patient_id {known["patient_id"]}', f'born {known["date_of_birth"]}',
                 f'plan on file: {known["insurer_on_file"]}' if known.get("insurer_on_file") else "no plan on file",
                 "has been seen here before" if known.get("has_visited_before") else "has never been seen here",
                 f'referrals on file: {", ".join(known["referrals_on_file"])}' if known.get("referrals_on_file") else "no referrals on file"]
        if known.get("note"):
            facts.append(f'chart note: {known["note"]}')
        lines.append(f'- Before ringing they filled in the page\'s form, and the clinic\'s records matched it: they are {known["full_name"]} '
                     f'({"; ".join(facts)}). They ARE identified and you greeted them by name already: never ask for their name, id, '
                     "date of birth or phone, and do not call find_patient for them — go straight to what they need. If they are "
                     "ringing for someone else, identify that person the usual way.")
    elif typed:
        missing = [_WORDS[k] for k in FIELDS if k not in screen.typed]
        lines.append(f"- Before ringing they typed this into the page's form — {typed}. "
                     + ("The clinic's records know nobody with these details. " if status == "not_found" else
                        "The records could not settle who they are from that alone. ")
                     + "Never ask again for anything typed there: use it as if they had just said it — in find_patient, and in "
                       "register_patient if they want to register"
                     + (f"; ask only for what is missing ({', '.join(missing)})." if missing else "; nothing is missing."))
    lines.append("- The page shows them a calendar with the free times you find. After find_slots, say the first option as always, then "
                 "add in a few words that the other free times are on their screen and they can tell you the day and time that suits "
                 "them. When they name a day and a time, call find_slots again with date_iso (or weekday) and at_time set to exactly "
                 "that, and offer what comes back. Never read a list of times aloud.")
    lines.append("- As you take their details, the page's form fills in by itself, so there is no need to read them back unless a tool says so.")
    return "\n".join(lines) + "\n"
