"""Pure logic, checked against facts the organizers published."""

from datetime import date, datetime

import pytest

from clinic_agent import dates, geo, ids
from clinic_agent.config import MADRID

# All 73 published cases are anchored to Friday 18 September 2026.
FRIDAY = date(2026, 9, 18)


# --- national ids: every id below is a published persona's, so its letter is known-good ---
@pytest.mark.parametrize("raw", ["48064716Y", "18921027P", "50454876Y", "31426012P", "X0500252W"])
def test_published_ids_are_valid(raw):
    assert ids.parse(raw).valid


@pytest.mark.parametrize(
    "raw, normalized",
    [("12345678-Z", "12345678Z"), ("12345678z", "12345678Z"), ("1234 5678 Z", "12345678Z"), ("x-1234567-l", "X1234567L")],
)
def test_normalization_matches_the_scorers_table(raw, normalized):
    assert ids.parse(raw).normalized == normalized
    assert ids.parse(raw).valid


def test_misheard_letter_is_caught_and_the_digits_name_the_right_one():
    heard = ids.parse("18921027B")  # P misheard as B
    assert not heard.valid
    assert heard.expected_letter == "P"
    assert heard.corrected == "18921027P"


def test_wrong_shape_is_invalid():
    assert not ids.parse("1892102P").valid
    assert ids.parse("1892102P").kind is None


# --- dates: the 'When Exactly' prompts state which date each phrase means ---
@pytest.mark.parametrize(
    "kind, weekday, iso, expected",
    [
        ("tomorrow", None, None, date(2026, 9, 19)),
        ("weekday", "thursday", None, date(2026, 9, 24)),  # "this coming Thursday"
        ("weekday", "saturday", None, date(2026, 9, 19)),  # "on Saturday morning"
        ("weekday", "sunday", None, date(2026, 9, 20)),  # "this coming Sunday"
        ("date", None, "2026-10-12", date(2026, 10, 12)),  # "Monday the twelfth of October"
        ("day_after_tomorrow", None, None, date(2026, 9, 20)),
        ("in_one_week", None, None, date(2026, 9, 25)),
        ("in_two_weeks", None, None, date(2026, 10, 2)),
    ],
)
def test_published_phrases_resolve(kind, weekday, iso, expected):
    assert dates.resolve_day(kind, FRIDAY, weekday, iso) == expected


def test_weekday_said_on_that_weekday_is_a_week_away():
    thursday = date(2026, 9, 17)
    assert dates.resolve_day("weekday", thursday, "thursday") == date(2026, 9, 24)
    assert dates.resolve_day("weekday", FRIDAY, "friday") == date(2026, 9, 25)


def test_earliest_has_no_day_and_never_means_today():
    assert dates.resolve_day("earliest", FRIDAY) is None
    assert dates.earliest_bookable(FRIDAY) == date(2026, 9, 19)


def test_morning_ends_at_fourteen_hundred():
    assert dates.in_part_of_day(datetime(2026, 9, 21, 13, 45, tzinfo=MADRID), "morning")
    assert not dates.in_part_of_day(datetime(2026, 9, 21, 14, 0, tzinfo=MADRID), "morning")
    assert dates.in_part_of_day(datetime(2026, 9, 21, 14, 0, tzinfo=MADRID), "afternoon")


# --- nearest site: coordinates from the clinic catalogue ---
SITES = [
    {"id": "centro", "latitude": 40.4178, "longitude": -3.7075},
    {"id": "norte", "latitude": 40.4645, "longitude": -3.6836},
    {"id": "sur", "latitude": 40.305, "longitude": -3.7327},
]


def test_getafe_is_nearest_to_sur_and_chamartin_to_norte():
    assert geo.sites_by_distance(40.3083, -3.7327, SITES)[0]["id"] == "sur"
    assert geo.sites_by_distance(40.4722, -3.6826, SITES)[0]["id"] == "norte"
    assert geo.sites_by_distance(40.4168, -3.7038, SITES)[0]["id"] == "centro"


# --- a tool call the model wrote as text instead of making (seen in the evals) is recovered at hang-up ---
async def test_leaked_register_call_is_recovered_at_the_end_of_the_call():
    from clinic_agent import tools
    from clinic_agent.session import CallSession

    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    s.heard = ["I am with Cigna."]
    s.said = ["cat=default_api:register_patient{date_of_birth: 1970-06-25 ,email: joaquingonzalez24@hotmail.com ,"
              "first_surname: González ,given_name: Joaquín ,insurer: cigna ,national_id: 18921027P ,"
              "phone: 783869132 ,second_surname: Ortega }", "You have been successfully registered with us."]
    await tools.finalize(s, api=None)
    assert s.submissions == [{"action": "register", "given_name": "Joaquín", "first_surname": "González",
                              "second_surname": "Ortega", "national_id": "18921027P", "date_of_birth": "1970-06-25",
                              "phone": "783869132", "email": "joaquingonzalez24@hotmail.com", "insurer": "cigna"}]


async def test_register_is_refused_once_when_the_caller_never_said_an_insurer():
    from clinic_agent import tools
    from clinic_agent.session import CallSession

    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    s.heard = ["Natalia Muñoz González.", "My DNI is 50454876Y."]
    fields = dict(given_name="Natalia", first_surname="Muñoz", second_surname="González", national_id="50454876Y",
                  date_of_birth="1988-12-13", phone="797574941", email="natalia.munoz86@hotmail.com")
    assert (await tools.register_patient(s, None, insurer="privado", **fields))["status"] == "insurer_not_heard"
    s.heard.append("I'm with Sanitas.")
    assert (await tools.register_patient(s, None, insurer="sanitas", **fields))["status"] == "recorded"


# --- the email's name part is repaired from the name we already hold (seen live: "jokeen gonzales 24 at hot mail") ---
@pytest.mark.parametrize("heard, expected", [
    ("jokeengonzalez24@hotmail.com", "joaquingonzalez24@hotmail.com"),
    ("joaquin gonzales 24 @ hot mail.com", "joaquingonzalez24@hotmail.com"),
    ("Joaquingonzalez24@Hotmail.com", "joaquingonzalez24@hotmail.com"),
])
def test_email_name_part_is_repaired(heard, expected):
    from clinic_agent.tools import repair_email
    assert repair_email(heard, "Joaquín", "González", "Ortega") == expected


def test_email_repair_keeps_separators_digits_and_unrelated_words():
    from clinic_agent.tools import repair_email
    assert repair_email("natalia.munos86@hotmail.com", "Natalia", "Muñoz", "González") == "natalia.munoz86@hotmail.com"
    assert repair_email("sergio_martines77@gmail.com", "Sergio", "Martínez", "Ramírez") == "sergio_martinez77@gmail.com"
    assert repair_email("bookworm12@icloud.com", "Elizabeth", "Jones", "Evans") == "bookworm12@icloud.com"


# --- line manners: half-sentences, and a reply the model writes twice (both seen on the real harness) ---
@pytest.mark.parametrize("heard, unfinished", [
    ("Yeah. So", True), ("I need a", True), ("My DNI is four eight zero", True), ("Nearly. The email is", True),
    ("Hello?", False), ("Chloe Roberts Smith.", False), ("12/09/1939.", False), ("Yes, please book it!", False), ("", False),
])
def test_a_turn_without_closing_punctuation_is_a_half_sentence(heard, unfinished):
    from clinic_agent.speech import looks_unfinished
    assert looks_unfinished(heard) is unfinished


def test_a_replayed_reply_is_dropped_whatever_the_chunking():
    from clinic_agent.speech import ReplayFilter
    f = ReplayFilter()
    chunks = ["Good", " morning. How can I help you today?", "Good morning.", " How can I help", " you today?"]
    assert "".join(f.feed(c) for c in chunks) == "Good morning. How can I help you today?"


def test_a_replay_that_starts_in_the_middle_of_a_chunk_is_dropped_too():
    from clinic_agent.speech import ReplayFilter
    f = ReplayFilter()  # exactly what the scored run streamed
    chunks = ["Good", " morning. How can I help you today?Good morning. How can I help you today?"]
    assert "".join(f.feed(c) for c in chunks) == "Good morning. How can I help you today?"


def test_a_reply_that_only_starts_like_itself_is_kept_whole():
    from clinic_agent.speech import ReplayFilter
    f = ReplayFilter()
    chunks = ["Monday the twenty-first at nine is taken. ", "Monday the twenty-first", " at nine thirty is free."]
    assert "".join(f.feed(c) for c in chunks) == "".join(chunks)
    g = ReplayFilter()
    assert "".join(g.feed(c) for c in ["Yes. ", "Yes, of course."]) == "Yes. Yes, of course."


# --- a booking request stays a booking, even when the patient already holds an appointment (seen live) ---
async def test_reschedule_is_questioned_once_when_the_caller_never_asked_to_move_anything():
    from clinic_agent import tools
    from clinic_agent.session import CallSession

    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    s.patients["P1"] = {"insurer": "cigna"}
    s.appointments["A1"] = {"appointment_id": "A1", "patient_id": "P1"}
    s.slots["S1"] = {"provider_id": "PR12", "location_id": "norte", "appointment_type_id": "dermatology_review",
                     "start_time": "2026-09-21T10:15:00+02:00", "payable_with": ["cigna"]}
    s.heard = ["I need a dermatology appointment for a rash on my arm.", "I'd like the earliest available, please."]
    assert (await tools.reschedule(s, None, "A1", "S1"))["status"] == "caller_did_not_ask_to_move"
    assert (await tools.book(s, None, "P1", "S1"))["status"] == "recorded"
    assert [a["action"] for a in s.submissions] == ["book"]

    moved = CallSession(call_id="t2", dry_run=True, persist_log=False)
    moved.patients, moved.appointments, moved.slots = s.patients, s.appointments, s.slots
    moved.heard = ["I can't make my appointment on Tuesday, what is the next time she has?"]
    assert (await tools.reschedule(moved, None, "A1", "S1"))["status"] == "recorded"


async def test_the_clock_alone_cannot_trigger_a_new_search_over_an_offer():
    from clinic_agent import tools
    from clinic_agent.session import CallSession

    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    s.patients["P1"] = {"insurer": "sanitas"}
    s.last_offered_slot, s.search_locked = "S4", True
    result = await tools.find_slots(s, None, "P1", specialty_id="general_practice")
    assert result["status"] == "no_time" and "S4" in result["say"]


# --- a tool call the model writes as text is never speech, and is recovered as the call it should have been ---
@pytest.mark.parametrize("written, name, args", [
    ("cat=default_api:find_patient,call:default_api:find_patient{name:Rachel Lewis Robinson,use_caller_id:true}",
     "find_patient", {"name": "Rachel Lewis Robinson", "use_caller_id": True}),
    ('padlocks: []\n```json\n{\n  "call": "default_api:find_patient",\n  "args": {\n    "name": "Sonia Iglesias Morales",\n'
     '    "use_caller_id": true\n  }\n}\n```', "find_patient", {"name": "Sonia Iglesias Morales", "use_caller_id": True}),
    ("cat=default_api:find_slots{day_kind:earliest,patient_id:P00005,specialty_id:orthopaedics}",
     "find_slots", {"day_kind": "earliest", "patient_id": "P00005", "specialty_id": "orthopaedics"}),
])
def test_written_tool_calls_from_the_scored_run_are_caught_and_parsed(written, name, args):
    from clinic_agent.speech import _NOT_SPEECH
    from clinic_agent.tools import parse_leaked_calls
    assert _NOT_SPEECH.search(written)
    assert parse_leaked_calls(written) == [(name, args)]


@pytest.mark.parametrize("spoken", [
    "The earliest appointment is with Dr. Tomás Vilar at Arenal Norte on Monday, September twenty-first at ten fifteen.",
    "I heard five, zero, four, five, four, eight, seven, six, Y. Is that correct?",
    "If this is an emergency, please hang up and call 112 now.",
    "La primera cita libre es el lunes veintiuno a las nueve. ¿Le viene bien?",
])
def test_ordinary_replies_count_as_speech(spoken):
    from clinic_agent.speech import _NOT_SPEECH
    from clinic_agent.tools import parse_leaked_calls
    assert not _NOT_SPEECH.search(spoken)
    assert parse_leaked_calls(spoken) == []


# --- the platform's submit endpoint timed out on 8 of 22 calls in a scored run; one attempt was all we made ---
async def test_a_submission_that_times_out_is_retried_until_it_lands():
    from clinic_agent import tools
    from clinic_agent.session import CallSession

    class FlakyApi:
        calls = 0

        async def submit(self, action, payload):
            self.calls += 1
            if self.calls < 3:
                raise TimeoutError("read timeout")
            return 200, {"ok": True}

    s = CallSession(call_id="t", persist_log=False)
    s.submissions = [{"action": "no-action", "reason": "no_availability"}]
    api = FlakyApi()
    await tools.finalize(s, api)
    assert api.calls == 3 and s.posted == [{"action": "no-action", "http": 200, "attempts": 3}]


async def test_an_identical_repeat_counts_as_delivered_and_a_rejection_is_not_retried():
    from clinic_agent import tools
    from clinic_agent.session import CallSession

    class Api:
        def __init__(self, status): self.status, self.calls = status, 0
        async def submit(self, action, payload):
            self.calls += 1
            return self.status, {}

    for status in (409, 422):
        s = CallSession(call_id="t", persist_log=False)
        s.submissions = [{"action": "no-action", "reason": "no_availability"}]
        api = Api(status)
        await tools.finalize(s, api)
        assert api.calls == 1 and s.posted[0]["http"] == status


# --- languages: the voice follows the language the reply is written in; a Catalan caller is recognised ---
@pytest.mark.parametrize("reply, current, expected", [
    ("The earliest appointment is with Dra. Carmen Ortiz Vidal at Arenal Centro on Monday.", "en", "en"),
    ("La primera cita libre es con el doctor Martín Sáez en Arenal Sur, el lunes veintiuno.", "en", "es"),
    ("¿Me puede decir su nombre completo?", "en", "es"),
    ("Perfecto.", "en", "es"),
    ("Thank you, Señor Vázquez.", "es", "en"),
    ("OK.", "es", "es"),  # nothing to go on: the voice stays as it is
])
def test_the_voice_follows_the_language_of_the_reply(reply, current, expected):
    from clinic_agent.languages import reply_language
    assert reply_language(reply, current) == expected


def test_a_catalan_caller_is_recognised_through_the_multilingual_models_spelling():
    from clinic_agent.languages import sounds_catalan
    heard_by_nova3_multi = "Bon dia. Voldría de mandar la 1º hora liura da traumatologia. Que mantengue algo amquipugui parlar en catalá."
    assert sounds_catalan([heard_by_nova3_multi])
    assert sounds_catalan(["Bon dia.", "Em dic Teresa López García."])
    assert not sounds_catalan(["Hola, buenos días. Quería pedir la primera cita libre de medicina general."])
    assert not sounds_catalan(["Hi, I'd like the earliest appointment with Dr. Sáez at Arenal Centro, please."])


# --- a refusal takes back the booking the caller walked away from, and never sits beside another action ---
class _Catalogue:
    async def catalogue(self):
        return {"providers": [{"id": "PR10", "specialty_id": "orthopaedics"}, {"id": "PR03", "specialty_id": "general_practice"}]}


def _session_with_a_booking():
    from clinic_agent.session import CallSession
    s = CallSession(call_id="t", dry_run=True, persist_log=False)
    s.patients["P3"] = {"insurer": "sanitas"}
    s.slots["S1"] = {"provider_id": "PR10", "location_id": "sur", "appointment_type_id": "orthopaedic_review",
                     "start_time": "2026-09-21T09:30:00+02:00", "payable_with": ["sanitas"]}
    return s


async def test_okay_then_no_mornings_then_nothing_free_ends_as_a_single_refusal():
    from clinic_agent import tools
    s, api = _session_with_a_booking(), _Catalogue()
    await tools.book(s, api, "P3", "S1")                      # the caller said "Okay"
    s.last_search = ("P3", "orthopaedics")                    # "I can't make mornings" → afternoon search → nothing
    await tools.end_without_booking(s, api, "no_availability")
    assert s.submissions == [{"action": "no-action", "reason": "no_availability"}]


async def test_a_refused_second_request_leaves_the_first_booking_alone():
    from clinic_agent import tools
    s, api = _session_with_a_booking(), _Catalogue()
    await tools.book(s, api, "P3", "S1")
    s.last_search = ("P3", "dermatology")                     # a second request, blocked by a rule
    await tools.end_without_booking(s, api, "referral_required")
    assert [a["action"] for a in s.submissions] == ["book"]


def test_two_exact_details_identify_the_patient_whatever_the_name_was_heard_as():
    from clinic_agent.tools import _two_exact_details
    assert _two_exact_details({"matched_fields": ["name", "phone", "date_of_birth"]})
    assert _two_exact_details({"matched_fields": ["national_id", "date_of_birth"]})
    assert not _two_exact_details({"matched_fields": ["name", "phone"]})  # a shared surname plus the caller's own number


# --- the line's own number is evidence even when the model forgets it; a sound id forgives a mangled name ---
class _Directory:
    """Two patients on one phone number, mother and child; an exact field that does not match excludes a record
    and a shared surname is flagged as a name match — both as the real directory does."""
    def __init__(self):
        base = {"has_visited_before": True, "insurer": "dkv", "referrals": [], "note": ""}
        self.records = [
            dict(base, patient_id="P00820", given_name="Alice", first_surname="Collins", second_surname="Davies",
                 national_id="Z7873425R", phone="600111222", date_of_birth="2001-04-05"),
            dict(base, patient_id="P00900", given_name="Amparo", first_surname="Medina", second_surname="Domínguez",
                 national_id="92641944Z", phone="600333444", date_of_birth="1996-12-17"),
            dict(base, patient_id="P00901", given_name="Sonia", first_surname="Álvarez", second_surname="Medina",
                 national_id="62819257R", phone="600555666", date_of_birth="2017-05-12"),
        ]

    async def directory(self, **query):
        from clinic_agent.tools import fold
        found = []
        for rec in self.records:
            exact = [k for k in ("national_id", "phone", "date_of_birth") if k in query]
            if any(query[k] != rec[k] for k in exact):
                continue
            said = set(fold(query.get("name", "")).split())
            named = bool(said & set(fold(f'{rec["given_name"]} {rec["first_surname"]} {rec["second_surname"]}').split()))
            if exact or named:
                found.append(dict(rec, matched_fields=(["name"] if "name" in query else []) + exact))
        return found


def _ringing_from(number):
    from clinic_agent.session import CallSession
    return CallSession(call_id="t", from_number=number, dry_run=True, persist_log=False)


async def test_a_sound_id_and_the_lines_own_number_identify_a_patient_whose_name_was_misheard():
    from clinic_agent import tools
    s = _ringing_from("600111222")
    first = await tools.find_patient(s, _Directory(), name="Alys Davis", use_caller_id=True)
    assert first["status"] == "not_found"                     # one exact detail and a name that is not hers: not enough
    found = await tools.find_patient(s, _Directory(), name="Alys Davis", national_id="Z7873425R")  # the model dropped use_caller_id
    assert (found["status"], found["patient_id"]) == ("identified", "P00820")


async def test_a_sound_id_forgives_a_mangled_name_from_any_phone_but_a_corrected_letter_does_not():
    from clinic_agent import tools
    found = await tools.find_patient(_ringing_from(None), _Directory(), name="Alys Davis", national_id="Z7873425R")
    assert (found["status"], found["patient_id"]) == ("identified", "P00820")
    wrong_letter = await tools.find_patient(_ringing_from(None), _Directory(), name="Alys Davis", national_id="Z7873425A")
    assert wrong_letter["status"] == "not_found"


async def test_a_mother_ringing_for_her_child_still_gets_the_child_not_herself():
    from clinic_agent import tools
    s = _ringing_from("600333444")                            # the mother's number; the child's record has its own
    by_name = await tools.find_patient(s, _Directory(), name="Sonia Álvarez Medina")
    assert (by_name["status"], by_name["patient_id"]) == ("one_field_only", "P00901")
    assert "caller" in by_name                                # and the model is told whose number it is
    with_birthday = await tools.find_patient(s, _Directory(), name="Sonia Álvarez Medina", date_of_birth="2017-05-12")
    assert (with_birthday["status"], with_birthday["patient_id"]) == ("identified", "P00901")


# --- "the next one" and a later move keep the doctor and the site; only the time moves ---
class _Diary:
    """Monday's GP slots as the clinic listed them on the scored call that went wrong; the real catalogue."""
    SLOTS = [("09:00", "PR03", "sur"), ("09:15", "PR01", "centro"), ("09:15", "PR03", "sur"), ("09:30", "PR03", "sur"),
             ("09:30", "PR07", "centro"), ("09:45", "PR03", "sur"), ("10:00", "PR07", "centro")]

    def __init__(self):
        self.asked = []

    async def catalogue(self):
        import json
        from clinic_agent import config
        return json.loads((config.ORGANIZERS_DIR / "clinic.json").read_text())

    async def availability(self, date_from, date_to, *, provider_id=None, specialty_id=None, location_id=None,
                           patient_id=None, insurers=None):
        self.asked.append({"provider_id": provider_id, "specialty_id": specialty_id, "location_id": location_id})
        names = {p["id"]: p["name"] for p in (await self.catalogue())["providers"]}
        return {"blocked": [], "slots": [
            {"provider_id": p, "provider_name": names[p], "specialty_id": "general_practice", "location_id": site,
             "appointment_type_id": "review", "start_time": f"2026-09-21T{hhmm}:00+02:00", "duration_minutes": 15,
             "payable_with": ["dkv"]}
            for hhmm, p, site in self.SLOTS
            if (not provider_id or p == provider_id) and (not location_id or site == location_id)]}


def _saturday_evening_call():
    from datetime import datetime
    from clinic_agent import config
    from clinic_agent.session import CallSession
    s = CallSession(call_id="t", dry_run=True, persist_log=False, now=datetime(2026, 9, 19, 19, 0, tzinfo=config.MADRID))
    s.patients["P00902"] = {"insurer": "dkv"}
    return s


async def test_the_next_one_stays_at_the_site_of_the_offer_they_turned_down():
    from clinic_agent import tools
    s, api = _saturday_evening_call(), _Diary()
    first = await tools.find_slots(s, api, "P00902", specialty_id="general_practice")
    assert [(o["when"], o["site"]) for o in first["offers"]] == [
        ("Monday 21 September at 09:00", "Arenal Sur"), ("Monday 21 September at 09:15", "Arenal Sur"),
        ("Monday 21 September at 09:30", "Arenal Sur")]                # not Centro's 09:15: marked wrong on a scored call
    # "That time doesn't work for me. What's the next one?" — the model passes the slot it offered
    nxt = await tools.find_slots(s, api, "P00902", after_appointment_id=first["offers"][0]["slot_ref"])
    assert api.asked[-1] == {"provider_id": None, "specialty_id": "general_practice", "location_id": "sur"}
    assert (nxt["offers"][0]["when"], nxt["offers"][0]["site"]) == ("Monday 21 September at 09:15", "Arenal Sur")


async def test_the_next_one_may_be_another_doctor_as_in_the_published_answer():
    from clinic_agent import tools
    s, api = _saturday_evening_call(), _Diary()
    first = await tools.find_slots(s, api, "P00902", specialty_id="general_practice", location_id="centro")
    assert [(o["when"], o["doctor"]) for o in first["offers"]][:2] == [
        ("Monday 21 September at 09:15", "Dra. Carmen Ortiz Vidal"), ("Monday 21 September at 09:30", "Dra. Laura Benítez Roca")]
    nxt = await tools.find_slots(s, api, "P00902", after_appointment_id=first["offers"][0]["slot_ref"])
    assert (nxt["offers"][0]["when"], nxt["offers"][0]["doctor"]) == ("Monday 21 September at 09:30", "Dra. Laura Benítez Roca")


async def test_a_later_move_keeps_the_doctor_and_site_of_the_appointment_and_is_not_questioned():
    from clinic_agent import tools
    s, api = _saturday_evening_call(), _Diary()
    s.heard.append("My father cannot go on Monday, what is there after it?")   # none of the usual move words
    s.appointments["A1"] = {"appointment_id": "A1", "patient_id": "P00902", "provider_id": "PR07", "location_id": "centro",
                            "start_time": "2026-09-21T09:30:00+02:00"}
    found = await tools.find_slots(s, api, "P00902", after_appointment_id="A1")     # no doctor, no site, no specialty
    assert api.asked[-1] == {"provider_id": "PR07", "specialty_id": None, "location_id": "centro"}
    assert found["offers"][0]["when"] == "Monday 21 September at 10:00"            # nothing at or before 09:30
    moved = await tools.reschedule(s, api, "A1", found["offers"][0]["slot_ref"])
    assert moved["status"] == "recorded" and s.submissions[0]["action"] == "reschedule"


def test_a_relative_who_cannot_make_it_is_asking_to_move():
    from clinic_agent import tools
    for said in ("He cannot make his appointment on Tuesday with Dra. Benítez.", "Mi madre no va a poder ir a su cita del martes."):
        s = _saturday_evening_call()
        s.heard.append(said)
        assert tools._caller_asked_to_move(s), said
    s = _saturday_evening_call()
    s.heard.append("I'd like the earliest appointment with a GP, please.")
    assert not tools._caller_asked_to_move(s)


# --- the call console reads the same event logs the calls write ---
def test_console_puts_a_decision_in_words_and_times_the_lookups():
    from clinic_agent.console import _in_words, _lookup_times
    assert _in_words({"action": "book", "patient_id": "P00004", "provider_id": "PR10", "location_id": "norte",
                      "slot": "2026-09-25T10:45:00+02:00"}) == "BOOK P00004 · PR10 · norte · 2026-09-25 10:45"
    assert _in_words({"action": "no-action", "reason": "no_availability"}) == "NO_ACTION no_availability"
    events = [{"kind": "tool_call", "name": "find_slots", "t": 10.0}, {"kind": "tool_result", "name": "find_slots", "t": 10.4}]
    assert [round(s, 1) for s in _lookup_times(events)] == [0.4]
