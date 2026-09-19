"""The tool layer against the real (read-only) clinic API, with no LLM in the loop.

Each row replays what a correct agent would ask the tools for on a published case,
with the clock pinned to the case's reference time, and checks the dry-run
submission against the published accepted answer. Needs PROSPER_API_KEY and network.
"""

import json
from datetime import datetime

import pytest

from clinic_agent import config, tools
from clinic_agent.clinic import ClinicClient
from clinic_agent.session import CallSession

pytestmark = pytest.mark.skipif(not config.PROSPER_API_KEY, reason="needs PROSPER_API_KEY in .env")

CASES = {c["id"]: c for c in json.loads((config.ORGANIZERS_DIR / "public-cases.json").read_text())["cases"]}


def by_problem(problem_id: str) -> list[dict]:
    return [c for c in CASES.values() if c["problem_id"] == problem_id]


def accepted(case: dict) -> list[list[dict]]:
    return [a["actions"] for a in case["expected"]["acceptable"]]


async def run(case: dict, *searches: dict) -> list[dict]:
    """Identify by national id, run the searches in order, book the first offer found."""
    api = ClinicClient()
    s = CallSession(call_id="dry", now=datetime.fromisoformat(case["reference_time"]), dry_run=True, persist_log=False)
    try:
        who = await tools.find_patient(s, api, name=case["persona"]["data"]["full_name"],
                                       national_id=case["persona"]["data"]["national_id"])
        assert who["status"] == "identified", who
        for search in searches:
            found = await tools.find_slots(s, api, who["patient_id"], **search)
            if found["status"] == "slots_found":
                await tools.book(s, api, who["patient_id"], found["offers"][0]["slot_ref"], insurer=search.get("insurer", ""))
                break
            if found["status"] in ("blocked", "provider_not_found", "no_availability") and search is searches[-1]:
                await tools.end_without_booking(s, api, found.get("reason", found["status"]))
        return [{k.upper() if k == "action" else k: v for k, v in sub.items()} for sub in s.submissions]
    finally:
        await api.aclose()


def matches(submitted: list[dict], case: dict) -> bool:
    verbs = {"book": "BOOK", "no-action": "NO_ACTION", "escalate": "ESCALATE", "cancel": "CANCEL",
             "reschedule": "RESCHEDULE", "register": "REGISTER"}
    ours = [{**{k: v for k, v in sub.items() if k != "ACTION"}, "action": verbs[sub["ACTION"]]} for sub in submitted]
    return any(ours == want for want in accepted(case))


SIMPLE = by_problem("simple_booking")
DOCTOR = by_problem("doctor_and_site")
WHEN = by_problem("when_exactly")
RULES = by_problem("the_rules")

ROWS = [
    # The Simple Booking
    (SIMPLE[0], [dict(specialty_id="general_practice")]),
    (SIMPLE[1], [dict(specialty_id="general_practice", location_id="centro")]),
    (SIMPLE[2], [dict(specialty_id="orthopaedics")]),
    (SIMPLE[3], [dict(specialty_id="general_practice", location_id="sur", day_kind="weekday", weekday="monday", part_of_day="morning")]),
    # The Doctor and the Site
    (DOCTOR[0], [dict(provider_name="Dra. Ortiz Vidal", location_id="centro")]),
    (DOCTOR[1], [dict(provider_name="Dr. Sáez", specialty_id="general_practice")]),
    (DOCTOR[2], [dict(provider_name="Dr. Requena", location_id="norte")]),  # on leave → same kind, same site
    (DOCTOR[3], [dict(provider_name="Dr. Sáez", specialty_id="general_practice", location_id="centro", day_kind="weekday", weekday="monday"),
                 dict(provider_name="Dr. Sáez", specialty_id="general_practice", location_id="centro")]),
    (DOCTOR[4], [dict(provider_name="Dr. Fuentes", specialty_id="orthopaedics")]),
    # When Exactly
    (WHEN[0], [dict(specialty_id="general_practice", day_kind="tomorrow")]),
    (WHEN[1], [dict(specialty_id="orthopaedics", day_kind="weekday", weekday="thursday")]),
    (WHEN[2], [dict(specialty_id="general_practice", day_kind="weekday", weekday="saturday", part_of_day="morning")]),
    (WHEN[3], [dict(specialty_id="general_practice", location_id="centro", day_kind="weekday", weekday="sunday")]),
    (WHEN[4], [dict(specialty_id="general_practice", location_id="centro", day_kind="date", date_iso="2026-10-12", part_of_day="morning")]),
    # The Rules
    (RULES[1], [dict(specialty_id="dermatology")]),  # no referral
    (RULES[2], [dict(specialty_id="gynaecology")]),  # plan covers nothing in it
    (RULES[3], [dict(provider_name="Dra. Iglesias", specialty_id="dermatology")]),  # DKV: redirect, not refusal
]


@pytest.mark.parametrize("case, searches", ROWS, ids=[f'{c["problem_id"]}:{c["id"][-6:]}' for c, _ in ROWS])
async def test_tools_reach_the_published_answer(case, searches):
    # The published answers are anchored to Friday 18 September; the live API stops listing a slot once its
    # real time has passed, so an answer on a day already gone can no longer be reached.
    from datetime import datetime, timezone
    slots = [a["slot"] for acc in case["expected"]["acceptable"] for a in acc["actions"] if a.get("slot")]
    if slots and all(datetime.fromisoformat(s) <= datetime.now(timezone.utc) for s in slots):
        pytest.skip("the published slot is in the past; the live API no longer lists it")
    submitted = await run(case, *searches)
    assert matches(submitted, case), f"\n  submitted: {submitted}\n  accepted:  {accepted(case)}\n  summary:   {case['summary']}"
