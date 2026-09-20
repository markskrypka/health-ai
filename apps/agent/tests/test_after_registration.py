"""What the agent is told once it has registered someone. Seen live with a human caller: "You are now registered. How
can I help you today?", a search with an invented patient id, a lookup that (rightly) found nobody — and then reasons
made up for the caller: "your registration was not completed", "I need a valid Spanish phone number". Twelve minutes.
The clinic's directory never changes during a call, so every tool reachable after a registration says what is true."""

from clinic_agent import tools
from clinic_agent.session import CallSession
from tests.test_logic import _Diary, _Directory

FIELDS = dict(given_name="Natalia", first_surname="Muñoz", second_surname="González", national_id="50454876Y",
              date_of_birth="1988-12-13", phone="797574941", email="natalia.munoz86@hotmail.com", insurer="sanitas")


async def _registered() -> CallSession:
    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    s.heard = ["Natalia Muñoz González.", "My DNI is 50454876Y.", "I'm with Sanitas."]
    said = await tools.register_patient(s, _Diary(), **FIELDS)
    assert said["status"] == "recorded"
    assert "NEXT call" in said["say"] and "NEVER say the registration failed" in said["say"]
    return s


async def test_the_lookup_that_cannot_find_them_says_that_is_how_it_should_be():
    s = await _registered()
    found = await tools.find_patient(s, _Directory(), name="Natalia Muñoz González", national_id="50454876Y")
    assert found["status"] == "not_found"
    assert "only shows a new patient after the call" in found["say"] and "do not register them again" in found["say"]


async def test_a_search_with_an_invented_id_is_told_why_there_is_no_id():
    s = await _registered()
    found = await tools.find_slots(s, _Diary(), "patient_50454876Y", specialty_id="general_practice")
    assert found["status"] == "new_patient_books_next_call" and "NEXT call" in found["say"]


async def test_a_refusal_after_the_registration_leaves_it_standing_and_says_so():
    s = await _registered()
    said = await tools.end_without_booking(s, _Diary(), "patient_not_found")
    assert [r["action"] for r in s.submissions] == ["register"]
    assert "The registration stands" in said["say"]


async def test_registering_the_same_person_again_changes_nothing_and_says_the_same():
    s = await _registered()
    again = await tools.register_patient(s, _Diary(), **FIELDS)
    assert again["status"] == "recorded" and "They ARE registered" in again["say"]
    assert [r["action"] for r in s.submissions] == ["register"]


async def test_a_call_without_a_registration_is_told_what_it_always_was():
    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    assert (await tools.find_patient(s, _Directory(), name="Nadia Desconocida Nueva"))["say"].startswith("No record matches. Re-check")
    assert (await tools.find_slots(s, _Diary(), "P12345", specialty_id="general_practice"))["say"] == "Identify the patient with find_patient first."
