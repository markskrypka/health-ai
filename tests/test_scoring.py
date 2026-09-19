"""Our copy of the pass rule, checked against the organizers' own normalization table."""

from evals import scoring

BOOK = {"action": "BOOK", "patient_id": "P00042", "provider_id": "PR05", "location_id": "sur",
        "appointment_type_id": "review", "slot": "2026-09-24T16:30:00+02:00", "policy_id": "sanitas"}
REGISTER = {"action": "REGISTER", "new_patient": {
    "given_name": "José", "first_surname": "García", "second_surname": "López", "national_id": "12345678Z",
    "date_of_birth": "1988-03-14", "phone": "612345678", "email": "ana.garcia@gmail.com", "insurer": "adeslas"}}


def ours_book(**over):
    base = {"action": "book", "patient_id": "P00042", "provider_id": "PR05", "location_id": "sur",
            "appointment_type_id": "review", "slot": "2026-09-24T16:30:00+02:00", "policy_id": "sanitas"}
    return {**base, **over}


def ours_register(**over):
    base = {"action": "register", "given_name": "José", "first_surname": "García", "second_surname": "López",
            "national_id": "12345678Z", "date_of_birth": "1988-03-14", "phone": "612345678",
            "email": "ana.garcia@gmail.com", "insurer": "adeslas"}
    return {**base, **over}


def test_exact_booking_passes():
    assert scoring.passes([ours_book()], [{"actions": [BOOK]}])


def test_slot_tolerance_is_seconds_and_timezone_only():
    assert scoring.passes([ours_book(slot="2026-09-24T16:30:07+02:00")], [{"actions": [BOOK]}])
    assert scoring.passes([ours_book(slot="2026-09-24T14:30:00+00:00")], [{"actions": [BOOK]}])
    assert not scoring.passes([ours_book(slot="2026-09-24T16:45:00+02:00")], [{"actions": [BOOK]}])


def test_ids_are_exact_and_enums_are_folded():
    assert not scoring.passes([ours_book(provider_id="pr05")], [{"actions": [BOOK]}])
    assert scoring.passes([ours_book(appointment_type_id="  Review  ")], [{"actions": [BOOK]}])


def test_registration_tolerances_from_the_table():
    ok = ours_register(given_name="jose", first_surname="López", second_surname="Garcia",  # order free, accents folded
                       national_id="12345678-z", phone="+34 612 345 678", email=" Ana.Garcia@Gmail.com ")
    assert scoring.passes([ok], [{"actions": [REGISTER]}])
    assert not scoring.passes([ours_register(email="ana.garcia@gmail.co")], [{"actions": [REGISTER]}])
    assert not scoring.passes([ours_register(national_id="12345679Z")], [{"actions": [REGISTER]}])


def test_membership_in_a_set_of_answers_and_no_silence():
    other = {**BOOK, "provider_id": "PR07", "location_id": "norte"}
    assert scoring.passes([ours_book(provider_id="PR07", location_id="norte")], [{"actions": [BOOK]}, {"actions": [other]}])
    assert not scoring.passes([], [{"actions": [BOOK]}])


def test_two_cancellations_in_any_order_and_nothing_extra():
    want = [{"actions": [{"action": "CANCEL", "appointment_id": "A1"}, {"action": "CANCEL", "appointment_id": "A2"}]}]
    assert scoring.passes([{"action": "cancel", "appointment_id": "A2"}, {"action": "cancel", "appointment_id": "A1"}], want)
    assert not scoring.passes([{"action": "cancel", "appointment_id": "A1"}], want)
    assert not scoring.passes([ours_book(), {"action": "no-action", "reason": "out_of_scope"}], [{"actions": [BOOK]}])


def test_refusal_reason_is_the_answer():
    want = [{"actions": [{"action": "NO_ACTION", "reason": "referral_required"}]}]
    assert scoring.passes([{"action": "no-action", "reason": "REFERRAL_REQUIRED"}], want)
    assert not scoring.passes([{"action": "no-action", "reason": "specialty_not_covered"}], want)
    assert scoring.diff([{"action": "no-action", "reason": "specialty_not_covered"}], want) == [
        "NO_ACTION.reason: submitted 'specialty_not_covered', accepted 'referral_required'"]
