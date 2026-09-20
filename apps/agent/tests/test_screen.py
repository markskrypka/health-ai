"""A call from the clinic's web page gets a screen; a phone call gets exactly what it always got."""

import json
from datetime import datetime

from clinic_agent import bot, config, prompt, screen, tools
from clinic_agent.session import CallSession
from tests.test_logic import _Diary, _Directory, _saturday_evening_call


def _catalogue() -> dict:
    return json.loads((config.ORGANIZERS_DIR / "clinic.json").read_text())


def _call(number=None) -> CallSession:
    return CallSession(call_id="t", from_number=number, dry_run=True, persist_log=False,
                       now=datetime(2026, 9, 19, 19, 0, tzinfo=config.MADRID))


# ---------------------------------------------------------------- the phone line does not change

def test_a_phone_call_is_told_and_offered_exactly_what_it_always_was():
    cat, s = _catalogue(), _call("+34600111222")
    system, greeting, schemas = bot.call_setup(cat, s, None, None)
    assert system == prompt.build(cat, s.now, True)
    assert greeting == bot.GREETING
    assert [(sc.name, sc.description, sc.properties, sc.required) for sc in schemas] == \
           [(name, desc, props, req) for name, (_, desc, props, req) in tools.TOOLS.items()]
    assert "at_time" not in json.dumps([sc.properties for sc in schemas])
    assert "SCREEN" not in system


def test_only_a_start_message_that_says_so_makes_a_web_call():
    assert screen.from_start({}) is None
    assert screen.from_start({"from_number": "+34600111222", "call_id": "x"}) is None
    assert screen.from_start({"screen": "0", "prefill": '{"name": "Ana"}'}) is None
    web = screen.from_start({"screen": "1", "prefill": json.dumps({"name": " Alice Collins Davies ", "phone": "", "colour": "blue"})})
    assert web.typed == {"name": "Alice Collins Davies"}
    assert screen.from_start({"screen": "1", "prefill": "{not json"}).typed == {}


# ---------------------------------------------------------------- the form, before the greeting

async def test_a_caller_who_filled_the_form_in_is_known_before_the_greeting():
    s, web = _call(), screen.Screen(typed={"name": "Alice Collins Davies", "national_id": "Z7873425R", "email": "alice@example.com"})
    known = await screen.identify(s, _Directory(), web)
    assert known["status"] == "identified" and known["patient_id"] == "P00820"
    assert [e["kind"] for e in s.events] == ["tool_call", "patient", "tool_result"]
    assert s.events[0]["by"] == "form" and "email" not in s.events[0]["args"]  # the directory is not asked about an email

    system, greeting, schemas = bot.call_setup(_catalogue(), s, web, known)
    assert greeting == "Clínica Arenal, good morning, Alice. How can I help you?"
    assert "patient_id P00820" in system and "never ask for their name" in system
    assert "at_time" in next(sc for sc in schemas if sc.name == "find_slots").properties
    assert "at_time" not in next(sc for sc in schemas if sc.name == "find_patient").properties


async def test_the_desk_gets_the_record_with_the_id_and_the_phone_masked():
    s = _call()
    await screen.identify(s, _Directory(), screen.Screen(typed={"name": "Alice Collins Davies", "national_id": "Z7873425R"}))
    card = next(e for e in s.events if e["kind"] == "patient")["card"]
    assert card["given_name"] == "Alice" and card["insurer"] == "dkv"
    assert card["national_id_masked"] == "•••••425R" and card["phone_masked"] == "••••••222"
    assert "Z7873425R" not in json.dumps(card) and "600111222" not in json.dumps(card)


async def test_someone_the_records_do_not_know_is_not_asked_again_for_what_they_typed():
    s = _call()
    web = screen.Screen(typed={"name": "Nadia Desconocida Nueva", "date_of_birth": "1990-01-01", "phone": "611222333"})
    known = await screen.identify(s, _Directory(), web)
    assert known["status"] == "not_found"
    system, greeting, _ = bot.call_setup(_catalogue(), s, web, known)
    assert greeting == bot.GREETING
    assert "full name: Nadia Desconocida Nueva" in system and "The clinic's records know nobody with these details" in system
    assert "ask only for what is missing (DNI or NIE, email address, insurer)" in system


async def test_an_empty_form_is_a_web_call_with_nothing_known():
    s, web = _call(), screen.Screen()
    assert await screen.identify(s, _Directory(), web) is None and s.events == []
    system, greeting, _ = bot.call_setup(_catalogue(), s, web, None)
    assert greeting == bot.GREETING and "calendar" in system and "typed" not in system


# ---------------------------------------------------------------- the calendar

async def test_the_whole_diary_behind_an_offer_goes_to_the_log_and_three_to_the_model():
    s, api = _saturday_evening_call(), _Diary()
    found = await tools.find_slots(s, api, "P00902", specialty_id="general_practice")
    assert len(found["offers"]) == 3
    shown = next(e for e in s.events if e["kind"] == "availability")
    assert len(shown["slots"]) == len(_Diary.SLOTS)
    assert shown["slots"][0] == {"start": "2026-09-21T09:00:00+02:00", "provider_id": "PR03", "provider": shown["slots"][0]["provider"],
                                 "location_id": "sur", "site": "Arenal Sur"}
    assert [e["kind"] for e in s.events].index("availability") < [e["kind"] for e in s.events].index("offer")


async def test_a_time_read_off_the_calendar_leads_the_offer():
    s, api = _saturday_evening_call(), _Diary()
    found = await tools.find_slots(s, api, "P00902", specialty_id="general_practice", location_id="centro", date_iso="2026-09-21", at_time="9:30")
    assert found["offers"][0]["when"].endswith("09:30") or "half past nine" in found["offers"][0]["when"]
    assert s.slots[found["offers"][0]["slot_ref"]]["start_time"] == "2026-09-21T09:30:00+02:00"


async def test_a_time_that_is_not_free_says_so_and_offers_the_nearest():
    s, api = _saturday_evening_call(), _Diary()
    found = await tools.find_slots(s, api, "P00902", specialty_id="general_practice", date_iso="2026-09-21", at_time="11:40")
    assert found["status"] == "slots_found" and any("Nothing is free at 11:40" in n for n in found["notes"])


async def test_only_a_caller_with_a_screen_is_pointed_at_it():
    on_the_phone, api = _saturday_evening_call(), _Diary()
    assert "screen" not in (await tools.find_slots(on_the_phone, api, "P00902", specialty_id="general_practice"))["say"]
    on_the_page = _saturday_evening_call()
    on_the_page.screen = True
    assert "on their screen" in (await tools.find_slots(on_the_page, api, "P00902", specialty_id="general_practice"))["say"]


async def test_a_web_caller_who_hangs_up_on_an_offer_has_not_booked_it_and_a_phone_caller_still_has():
    for on_the_page, expected in ((True, []), (False, ["book"])):
        s, api = _saturday_evening_call(), _Diary()
        s.screen = on_the_page
        await tools.find_slots(s, api, "P00902", specialty_id="general_practice")
        await tools.finalize(s, api)
        assert [r["action"] for r in s.submissions] == expected
