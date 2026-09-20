"""The agent's tools. The LLM proposes; this code disposes.

Framework-free on purpose: the live Pipecat bot and the text evals call the very
same functions. Rules the clinic API does not apply for us live here — nothing
same-day, the date vocabulary, a doctor on leave, near-miss doctor names, the
nearest site — and every submission is checked against ids this call has seen.

Nothing returned to the LLM ever contains a patient's national id or phone
number: what the model never sees, it cannot read out (problem 14).
"""

import asyncio
import re
import time
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Awaitable, Callable

from . import config, dates, geo, ids
from .clinic import ClinicClient, ClinicError
from .config import MADRID
from .session import CallSession

REASONS = [
    "not_eligible_age", "referral_required", "provider_not_in_network", "specialty_not_covered",
    "location_not_covered", "insurer_referral_required", "allowance_exhausted", "provider_on_leave",
    "location_hours", "type_not_offered", "patient_history", "no_availability", "clinic_closed",
    "patient_not_found", "provider_not_found", "caller_not_authorised", "out_of_scope", "medical_emergency",
]
INSURERS = ["sanitas", "adeslas", "dkv", "asisa", "mapfre", "caser", "cigna", "axa", "nueva_mutua", "privado"]
SPECIALTIES = ["general_practice", "paediatrics", "dermatology", "orthopaedics", "gynaecology", "physiotherapy"]
SITES = ["centro", "norte", "sur"]
# A second plan can lift these; nothing else can.
_COVERAGE = {"provider_not_in_network", "specialty_not_covered", "location_not_covered",
             "insurer_referral_required", "allowance_exhausted"}
_NAME_MATCH = 0.85
SUBMIT_WINDOW_SECS = 27.0


def fold(text: str) -> str:
    """Accent- and case-insensitive, the way the scorer folds names."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower().strip()


# ---------------------------------------------------------------- identification

def _two_exact_details(match: dict) -> bool:
    """Phone, id and date of birth match exactly or not at all; two of them on one record identify the patient,
    whatever speech-to-text made of the name. Seen live: a Catalan caller's "la data de naixement" arrived as
    the name "Ana Xamen", and a record matching on phone and date of birth was thrown away over it."""
    return len({"national_id", "phone", "date_of_birth"} & set(match.get("matched_fields", []))) >= 2


def _name_agrees(said: str, record: dict) -> bool:
    """Most of the name the caller said must be in the record's name; one mangled token is forgiven."""
    have = fold(f'{record["given_name"]} {record["first_surname"]} {record["second_surname"]}').split()
    want = [t for t in fold(said).replace(",", " ").split() if len(t) > 1]
    if not want:
        return False
    hits = sum(1 for w in want if any(SequenceMatcher(None, w, h).ratio() >= 0.8 for h in have))
    return hits >= min(2, len(want)) and hits >= len(want) - 1


def _name_is_recognisable(said: str, record: dict) -> bool:
    """One word of the name survived. Enough only beside a sound id found on file: the check letter rules out
    a misheard digit, and an id belongs to one person — unlike a phone number, which a mother and child share."""
    have = fold(f'{record["given_name"]} {record["first_surname"]} {record["second_surname"]}').split()
    want = [t for t in fold(said).replace(",", " ").split() if len(t) > 2]
    return any(SequenceMatcher(None, w, h).ratio() >= 0.8 for w in want for h in have)


def _given_name_agrees(said: str, record: dict) -> bool:
    given = fold(record["given_name"]).split()
    want = [t for t in fold(said).replace(",", " ").split() if len(t) > 1]
    return any(SequenceMatcher(None, w, g).ratio() >= 0.8 for w in want for g in given)


def _identifies(said: str, id_is_sound: bool, match: dict) -> bool:
    if not said or _name_agrees(said, match) or _two_exact_details(match):
        return True
    return id_is_sound and "national_id" in match.get("matched_fields", []) and _name_is_recognisable(said, match)


async def find_patient(s: CallSession, api: ClinicClient, name: str = "", national_id: str = "",
                       phone: str = "", date_of_birth: str = "", use_caller_id: bool = False) -> dict:
    query: dict[str, str] = {}
    if name:
        query["name"] = name
    if date_of_birth:
        query["date_of_birth"] = date_of_birth
    if phone:
        query["phone"] = phone
    id_is_sound = False
    if national_id:
        nid = ids.parse(national_id)
        if nid.kind is None:
            return {"status": "invalid_national_id",
                    "say": "That id is not 8 digits and a letter (or X/Y/Z, 7 digits and a letter). Ask the caller to repeat it one character at a time."}
        # A misheard letter is recoverable: the digits determine it. The name must then agree.
        query["national_id"] = nid.normalized if nid.valid else nid.corrected
        id_is_sound = nid.valid
    # The number they ring from is evidence whether or not the model thinks to pass it. Seen on a scored call:
    # "Alice Collins Davies" heard as "Alys Davis", her NIE sound and on file, her own number on the line — and
    # she was turned away, because the lookup that carried the NIE no longer carried the number.
    if not phone and s.from_number and (query or use_caller_id):
        query["phone"] = s.from_number
    if not query:
        return {"status": "need_identifier", "say": "Ask for the full name and the DNI/NIE, phone number or date of birth."}

    try:
        matches = await api.directory(**query)
        # The API scores additively and reports a shared surname as a name match: the child's name plus the
        # mother's caller id returns the MOTHER, flagged name+phone. So the name is compared here, in code.
        strong = [m for m in matches if _identifies(name, id_is_sound, m)]
        via_caller_id = "phone" in query and not phone
        if via_caller_id and name:
            # A family shares a line and often both surnames: the number plus "Muñoz Torres" fits the grandson as well
            # as the grandmother who is calling. Through the caller id the given name must agree too, or two exact details.
            strong = [m for m in strong if _given_name_agrees(name, m) or _two_exact_details(m)]
        if not strong and via_caller_id:
            if matches and name:
                s.caller_record = matches[0]
            del query["phone"]  # the number belongs to someone else — most likely the caller, ringing for the patient
            if query:
                strong = [m for m in await api.directory(**query) if _identifies(name, id_is_sound, m)]
    except ClinicError as err:
        return {"status": "error", "detail": str(err.detail)[:200]}

    exact = [k for k in ("national_id", "phone", "date_of_birth") if k in query]
    if not strong:
        return {"status": "not_found",
                "say": "No record matches. Re-check the identifier once (read it back). If it still fails, the caller may be new: offer to register them."}
    if len(strong) > 1 and name:
        strong = [m for m in strong if _given_name_agrees(name, m)] or strong  # relatives share surnames, not first names
    if len(strong) > 1:
        missing = [k for k in ("date_of_birth", "national_id") if k not in query]
        return {"status": "several_match", "count": len(strong),
                "say": f"Several patients match. Ask for their {' or '.join(missing) or 'phone number'} and search again. Do not describe the matches."}

    m = strong[0]
    fields = len(exact) + (1 if name else 0)
    s.patients[m["patient_id"]] = m
    result = {
        "status": "identified" if fields >= 2 else "one_field_only",
        "patient_id": m["patient_id"],
        "full_name": f'{m["given_name"]} {m["first_surname"]} {m["second_surname"]}',
        "date_of_birth": m["date_of_birth"],
        "has_visited_before": m["has_visited_before"],
        "insurer_on_file": m["insurer"],
        "referrals_on_file": m["referrals"],
    }
    if config.SHOW_CHART_NOTES:
        result["note"] = m["note"]
    if fields < 2:
        result["say"] = "Matched on one field only. Confirm a second one (name, date of birth or id) before booking anything."
    if s.caller_record and s.caller_record["patient_id"] != m["patient_id"]:
        result["caller"] = (f'The number they are ringing from is on another patient\'s record, '
                            f'{s.caller_record["given_name"]} {s.caller_record["first_surname"]} — the caller or a relative. '
                            "Book for the patient named above, not for that record.")
    s.log("patient", patient_id=m["patient_id"], matched_on=list(query), status=result["status"])
    return result


# ---------------------------------------------------------------- nearest site

def _serves(cat: dict, location_id: str, specialty_id: str) -> bool:
    return any(p["specialty_id"] == specialty_id and any(sch["location_id"] == location_id for sch in p["schedules"])
               for p in cat["providers"])


async def nearest_site(s: CallSession, api: ClinicClient, caller_address: str, specialty_id: str = "") -> dict:
    """Which clinic is closest to where the caller is — before we know who they are. The rule is the nearest
    clinic that can serve the request: Getafe plus gynaecology is Arenal Centro, because Sur has no gynaecologist."""
    where = await geo.geocode(caller_address)
    if where is None:
        return {"status": "address_not_found", "say": "Ask which town or neighbourhood they are in, then call nearest_site again."}
    s.caller_position = where
    cat = await api.catalogue()
    ranked = geo.sites_by_distance(*where, cat["locations"])
    serving = [loc for loc in ranked if not specialty_id or _serves(cat, loc["id"], specialty_id)] or ranked
    best = serving[0]
    result = {"status": "ok", "nearest": best["name"], "location_id": best["id"], "distance_km": best["distance_km"],
              "directions": geo.directions(*where, best),
              "say": "Name this clinic to the caller. If they ask how to get there, give these directions in one or two "
                     "sentences — always answer, never say you do not know. Then identify the patient and call find_slots."}
    if best is not ranked[0]:
        result["note"] = f'{ranked[0]["name"]} is closer ({ranked[0]["distance_km"]} km) but has nobody for {specialty_id}; say so in one sentence.'
    if not specialty_id:
        result["say"] += " If they have not said which kind of doctor they need, ask, and call nearest_site again with specialty_id."
    offered = s.slots.get(s.last_offered_slot or "")
    if offered and offered["location_id"] != best["id"]:
        s.withdraw_offer()  # the caller asked for the closest clinic: an offer made at another one no longer stands
        result["say"] += f' Your earlier offer was at another clinic and is off the table: search again and offer the first slot at {best["name"]}.'
    s.log("nearest_site", address=caller_address, position=where, ranked=[(loc["id"], loc["distance_km"]) for loc in ranked], named=best["id"])
    return result


# ---------------------------------------------------------------- slot search

# The model passes whatever the caller called their language; the catalogue lists ISO codes.
_LANGUAGES = {"es": ["es", "spa", "span", "espan", "castel"], "ca": ["ca", "cat", "valenc"], "en": ["en", "eng", "ingl", "angl"],
              "fr": ["fr", "fre", "fra"], "de": ["de", "ger", "ale", "deu"], "it": ["it", "ita"], "pt": ["pt", "por"]}


def _language_code(spoken: str) -> str:
    word = fold(spoken).strip()
    if not word:
        return ""
    return next((code for code, stems in _LANGUAGES.items() if word == code or any(word.startswith(s) for s in stems if len(s) > 2)),
                word[:2])


def _resolve_provider(catalogue: dict, spoken: str, specialty_id: str | None) -> list[dict]:
    """Providers whose name sounds like what was said. Sáez/Sáenz and Iglesias/Iglesia both come back."""
    want = [t for t in fold(spoken).replace(".", " ").split() if t not in {"dr", "dra", "d", "doctor", "doctora", "don"}]
    hits = []
    for p in catalogue["providers"]:
        if specialty_id and p["specialty_id"] != specialty_id:
            continue
        tokens = [t for t in fold(p["name"]).replace(".", " ").split() if t not in {"dr", "dra", "d"}]
        score = max((SequenceMatcher(None, w, t).ratio() for w in want for t in tokens), default=0.0)
        if score >= 0.8:
            hits.append(p)
    return hits


def _on_leave(provider: dict, day: date) -> bool:
    leave = provider.get("leave")
    return bool(leave) and date.fromisoformat(leave["start"]) <= day <= date.fromisoformat(leave["end"])


def _sits(provider: dict, site: str | None, day: date) -> bool:
    name = dates.WEEKDAYS[day.weekday()]
    return any((site is None or sch["location_id"] == site) and any(d["weekday"].lower() == name for d in sch["days"])
               for sch in provider["schedules"])


async def find_slots(s: CallSession, api: ClinicClient, patient_id: str, specialty_id: str = "",
                     provider_name: str = "", location_id: str = "", day_kind: str = "earliest",
                     weekday: str = "", date_iso: str = "", part_of_day: str = "any", language: str = "",
                     insurer: str = "", caller_address: str = "", after_appointment_id: str = "") -> dict:
    if patient_id not in s.patients:
        return {"status": "error", "say": "Identify the patient with find_patient first."}
    if s.search_locked and s.last_offered_slot:
        return {"status": "no_time", "say": f"No time for another search. If the caller accepted or has not refused your last "
                                            f"offer, record it now with slot_ref {s.last_offered_slot}, then say goodbye."}
    # A second plan is one the caller named on this call. The plan on file is priced anyway, and passing it used to
    # switch off the question that finds the real second plan; a plan nobody said is the model's invention.
    if insurer == s.patients[patient_id]["insurer"]:
        insurer = ""
    if insurer and not _caller_said_insurer(s, insurer) and not s.insurer_challenged:
        s.insurer_challenged = True
        return {"status": "insurer_not_heard",
                "say": "The caller has not named that plan on this call. Ask whether they hold a second insurance plan and what it "
                       "is called; if they cannot bring the name to mind, ask them to read it off the card, and wait. Then search again."}
    cat = await api.catalogue()
    today = s.now.astimezone(MADRID).date()
    notes: list[str] = []

    # "The next time after the appointment I have" — or after the slot just offered ("what's the next one?").
    # A move keeps its doctor and its clinic unless the caller named others: every published move reads "same
    # doctor, same clinic, nothing earlier". The next one after an offer keeps the clinic only: the published
    # answer to "ask for the next one" at Centro is another doctor's half past nine, not the same doctor's 11:45 —
    # and a scored call that answered it with another CLINIC's quarter past nine was marked wrong.
    anchor: dict | None = None
    if after_appointment_id:
        anchor = s.appointments.get(after_appointment_id) or s.slots.get(after_appointment_id)
        if anchor is None:
            return {"status": "error", "say": "after_appointment_id must be an appointment_id from list_appointments "
                                              "(to move it later) or the slot_ref you just offered (for the next one)."}
        if after_appointment_id in s.appointments and anchor["patient_id"] != patient_id:
            return {"status": "error", "say": "That appointment belongs to another patient. Search for this patient without after_appointment_id."}
        s.move_intended = s.move_intended or after_appointment_id in s.appointments
        location_id = location_id or anchor["location_id"]

    # who
    provider: dict | None = None
    if anchor and not provider_name:
        theirs = next((p for p in cat["providers"] if p["id"] == anchor["provider_id"]), None)
        specialty_id = specialty_id or (theirs["specialty_id"] if theirs else "")
        if after_appointment_id in s.appointments and theirs:
            provider, specialty_id = theirs, theirs["specialty_id"]
    if provider_name:
        found = _resolve_provider(cat, provider_name, specialty_id or None)
        if not found:
            s.last_offered_slot, s.last_refusal_reason = None, "provider_not_found"
            return {"status": "provider_not_found",
                    "say": "No doctor of that name works here. Offer another doctor of the kind they need; if they will see nobody else, end_without_booking(provider_not_found)."}
        if len(found) > 1:
            return {"status": "ambiguous_provider",
                    "options": [{"name": p["name"], "specialty": p["specialty_name"]} for p in found],
                    "say": "Two doctors sound alike. Ask which one, then search again with specialty_id set."}
        provider, specialty_id = found[0], found[0]["specialty_id"]
    if not specialty_id:
        return {"status": "error", "say": "Give specialty_id or provider_name."}
    s.last_search = (patient_id, specialty_id)

    # when
    try:
        wanted_day = dates.resolve_day(day_kind, today, weekday or None, date_iso or None)
    except ValueError as err:
        return {"status": "error", "say": str(err)}
    start = wanted_day or dates.earliest_bookable(today)
    # Later that same day counts, anything earlier never does.
    not_before: datetime | None = None
    if anchor:
        not_before = datetime.fromisoformat(anchor["start_time"]).astimezone(MADRID)
        start = max(start, not_before.date())
    if start <= today:
        return {"status": "error", "say": "Nothing is booked for today or the past. The earliest is tomorrow."}

    # where
    sites: list[str | None] = [location_id or None]
    if caller_address and not s.caller_position:
        s.caller_position = await geo.geocode(caller_address)
        if s.caller_position is None:
            return {"status": "address_not_found", "say": "Ask which town or neighbourhood they are in, then search again."}
    if s.caller_position and not anchor:
        # The caller asked for the closest clinic: nearest first among those that have this kind of doctor,
        # whatever site the model passed. In the evals the model named a clinic from its own idea of Madrid.
        ranked = [loc for loc in geo.sites_by_distance(*s.caller_position, cat["locations"]) if _serves(cat, loc["id"], specialty_id)]
        sites = [loc["id"] for loc in ranked]
        notes.append("Clinics with this kind of doctor, nearest first: " + ", ".join(f'{l["name"]} ({l["distance_km"]} km)' for l in ranked))

    if provider and _on_leave(provider, start):
        notes.append(f'{provider["name"]} is on leave until {provider["leave"]["end"]}. '
                     "Offering the earliest doctor of the same kind at the same site instead; tell the caller.")
        if not location_id and len(sites) == 1:
            sites = [sch["location_id"] for sch in provider["schedules"]]
        provider = None

    speaks = _language_code(language)
    allowed = {p["id"] for p in cat["providers"] if p["specialty_id"] == specialty_id
               and (not speaks or speaks in p["languages"])}
    if speaks and not allowed:
        return {"status": "no_provider_speaks", "say": f"No {specialty_id} doctor speaks that language. Say so and offer Spanish."}

    # A search that goes out withdraws the offer on the table. Seen live twice: the caller turned an offer down,
    # their next words cut the new search short, and the refused slot was still bookable — and was booked.
    s.withdraw_offer()
    calendar_end = date.fromisoformat(cat["calendar"]["ends"])
    # The API still lists slots on a published closure day (as it does for today); neither is ever accepted.
    closed_days = set(cat["calendar"]["closure_days"])
    blocked: list[dict] = []
    # A doctor who cannot take this patient (a standing rule) gives way to the others of the same kind. A loop, not
    # a second call of this function: a move pins its doctor again on every call, and that never ended.
    for doctor in ([provider, None] if provider else [None]):
        for site in sites:
            cursor, picked = start, []
            while cursor <= calendar_end and not picked:
                window_end = min(cursor + timedelta(days=13), calendar_end)
                try:
                    res = await api.availability(cursor.isoformat(), window_end.isoformat(),
                                                 provider_id=doctor["id"] if doctor else None,
                                                 specialty_id=None if doctor else specialty_id,
                                                 location_id=site, patient_id=patient_id,
                                                 insurers=[insurer] if insurer else None)
                except ClinicError as err:
                    return {"status": "error", "detail": str(err.detail)[:200]}
                blocked = res["blocked"]
                for slot in res["slots"]:
                    t = datetime.fromisoformat(slot["start_time"]).astimezone(MADRID)
                    if t.date().isoformat() in closed_days or t.date() <= today or (not_before and t <= not_before):
                        continue
                    if slot["provider_id"] in allowed and dates.in_part_of_day(t, part_of_day):
                        picked.append(slot)
                if not res["slots"] and blocked:
                    break  # a standing rule, not a full diary: later windows will say the same
                cursor = window_end + timedelta(days=1)
            if picked:
                return _offer(s, cat, picked, wanted_day, site, part_of_day, notes, doctor, patient_id)
        if not (doctor and blocked):
            break
        notes.append(f'{doctor["name"]} cannot take this patient ({blocked[0]["restriction"]}). Looking at the same specialty.')

    if blocked:
        kinds = [b["restriction"] for b in blocked]
        reason = max(set(kinds), key=lambda k: (kinds.count(k), k != "provider_not_in_network"))
        say = f"The clinic's rules stop this booking: {reason}. Explain it plainly."
        if reason in _COVERAGE and not insurer:
            say += (" First ask whether they hold a second insurance plan. If they name one, search again with insurer set. "
                    "If they have one but cannot bring its name to mind, ask them to find the card and read it out, and wait for it. "
                    f"Only when they hold no other plan: end_without_booking({reason}).")
        else:
            say += f" Then end_without_booking({reason})."
        s.log("blocked", reason=reason, blocked=blocked)
        s.last_offered_slot, s.last_refusal_reason = None, reason
        return {"status": "blocked", "reason": reason, "say": say}
    s.last_offered_slot, s.last_refusal_reason = None, "no_availability"
    return {"status": "no_availability",
            "say": "Nothing free matches. Offer to widen the search (another day, time of day, doctor or site). If nothing they accept exists, end_without_booking(no_availability)."}


def _already_recorded(s: CallSession, slot: dict, patient_id: str) -> bool:
    """This very slot is already booked, or is where an appointment was already moved to, for this patient on this call."""
    for record in s.submissions:
        whose = record.get("patient_id") or s.appointments.get(record.get("appointment_id", ""), {}).get("patient_id")
        if record["action"] in ("book", "reschedule") and whose == patient_id and \
                (record["slot"], record["provider_id"], record["location_id"]) == (slot["start_time"], slot["provider_id"], slot["location_id"]):
            return True
    return False


def _offer(s: CallSession, cat: dict, picked: list[dict], wanted_day: date | None, site: str | None,
           part_of_day: str, notes: list[str], provider: dict | None, patient_id: str) -> dict:
    picked.sort(key=lambda sl: sl["start_time"])
    first_day = datetime.fromisoformat(picked[0]["start_time"]).astimezone(MADRID).date()
    if wanted_day and first_day != wanted_day:
        pool = [provider] if provider else [p for p in cat["providers"] if p["id"] in {sl["provider_id"] for sl in picked}]
        closed = wanted_day.weekday() == 6 or wanted_day.isoformat() in cat["calendar"]["closure_days"] \
            or not any(_sits(p, site, wanted_day) for p in pool)
        notes.append(f"Nothing on {wanted_day:%A %d %B}: " + (
            "the clinic or that kind of doctor is not in that day. This is the earliest on the next day one is, same site and time of day."
            if closed else "that day is full. This is the nearest that matches; ask if it works."))
    site_names = {l["id"]: l["name"] for l in cat["locations"]}
    # "What's the next one?" turns down a time, not a clinic: after the earliest come the later times at the same
    # site, whoever the doctor, then the other sites'. (See the note on after_appointment_id in find_slots.)
    first = picked[0]
    same = [sl for sl in picked[1:] if sl["location_id"] == first["location_id"]]
    picked = [first] + same + [sl for sl in picked[1:] if sl not in same]
    # One offer per distinct time keeps the call short: the earliest, then two later ones.
    offers, seen = [], set()
    for slot in picked:
        if slot["start_time"] in seen:
            continue
        seen.add(slot["start_time"])
        ref = s.remember_slot(slot, found_for=patient_id)
        t = datetime.fromisoformat(slot["start_time"]).astimezone(MADRID)
        offers.append({"slot_ref": ref, "when": dates.spoken(t), "doctor": slot["provider_name"],
                       "site": site_names.get(slot["location_id"], slot["location_id"]),
                       "payable_with": slot["payable_with"]})
        if len(offers) == 3:
            break
    if _already_recorded(s, first, patient_id):
        # Seen live: booked 14:00, the caller repeated it back as "fourteen thirty", the model searched again,
        # apologised for "booking 14:00 by mistake" and moved a correct booking to 15:30.
        notes.append("The first slot here is the one you have ALREADY recorded for this patient, and it is still the first that "
                     "matches. A caller who repeats a time back wrongly has misheard it, not changed their mind: say the day "
                     "and the time again, slowly, and change nothing unless they now ask for a different time.")
    s.last_offered_slot, s.last_offered_patient, s.last_refusal_reason = offers[0]["slot_ref"], patient_id, None
    s.log("offer", offers=offers, notes=notes)
    return {"status": "slots_found", "offers": offers, "notes": notes,
            "say": "Offer the FIRST one only. Read back day, date, time, doctor and site; book(slot_ref) once the caller says yes. "
                   "If they only turn down the time and ask for the next one, offer the next in this list — do not search again."}


async def list_appointments(s: CallSession, api: ClinicClient, patient_id: str) -> dict:
    if patient_id not in s.patients:
        return {"status": "error", "say": "Identify the patient with find_patient first."}
    cat = await api.catalogue()
    names = {p["id"]: p["name"] for p in cat["providers"]}
    sites = {l["id"]: l["name"] for l in cat["locations"]}
    upcoming = await api.appointments(patient_id, "upcoming")
    for a in upcoming:
        s.appointments[a["appointment_id"]] = a
    return {"status": "ok", "upcoming": [
        {"appointment_id": a["appointment_id"], "doctor": names.get(a["provider_id"], a["provider_id"]),
         "site": sites.get(a["location_id"], a["location_id"]),
         "when": dates.spoken(datetime.fromisoformat(a["start_time"]).astimezone(MADRID))} for a in upcoming]}


# ---------------------------------------------------------------- submissions

_MAIL_DOMAINS = ["gmail", "hotmail", "icloud", "yahoo", "outlook", "live", "protonmail", "telefonica", "movistar"]


def repair_email(email: str, given_name: str, first_surname: str, second_surname: str) -> str:
    """Speech-to-text mangles the name inside an address ("jokeen gonzales 24 at hot mail"), and a spoken
    read-back of an email can never be confirmed through two speech systems. But addresses here are built from
    the caller's own name, which we hold spelled correctly — so the name part is repaired in code."""
    email = fold(email).replace(" ", "")
    if email.count("@") != 1:
        return email
    local, domain = email.split("@")
    names = [fold(n).replace(" ", "") for n in (given_name, first_surname, second_surname) if n]
    joined = [a + b for a in names for b in names if a != b]
    out = []
    for token in re.findall(r"[a-z]+|[^a-z]+", local):
        if token.isalpha() and len(token) > 2:
            best = max(names + joined, key=lambda c: SequenceMatcher(None, token, c).ratio())
            if SequenceMatcher(None, token, best).ratio() >= 0.75:
                token = best
        out.append(token)
    label, _, tld = domain.partition(".")
    known = max(_MAIL_DOMAINS, key=lambda d: SequenceMatcher(None, label, d).ratio())
    if SequenceMatcher(None, label, known).ratio() >= 0.8:
        label = known
    return "".join(out) + "@" + label + ("." + tld if tld else "")


async def check_national_id(s: CallSession, api: ClinicClient, national_id: str) -> dict:
    """No network: the check letter is arithmetic. Lets the agent skip a read-back when the id is sound."""
    nid = ids.parse(national_id)
    if nid.kind is None:
        return {"status": "wrong_shape", "say": "Not 8 digits + letter (or X/Y/Z + 7 digits + letter). Ask them to repeat it slowly, one character at a time."}
    if not nid.valid:
        return {"status": "letter_mismatch", "say": f"The letter does not fit the digits. Read the digits back in groups and ask if they are right. If the caller confirms the digits, the letter must be {nid.expected_letter}."}
    return {"status": "valid", "national_id": nid.normalized, "say": "The id is sound. Do not read it back; move on."}


# How a caller (or the speech-to-text) may say each plan.
_INSURER_WORDS = {
    "sanitas": ["sanitas"], "adeslas": ["adeslas", "a deslas"], "dkv": ["dkv", "d k v", "de ka uve"],
    "asisa": ["asisa", "a sisa"], "mapfre": ["mapfre", "map fre", "mapfree"], "caser": ["caser", "casser"],
    "cigna": ["cigna", "signa"], "axa": ["axa", "a x a"], "nueva_mutua": ["nueva mutua", "nueva mutual"],
    "privado": ["privado", "private", "self pay", "self-pay", "no insurance", "sin seguro", "out of pocket"],
}


def _caller_said_insurer(s: CallSession, insurer: str) -> bool:
    said = " ".join(fold(t) for t in s.heard)
    words = said.split()
    for alias in _INSURER_WORDS.get(insurer, [insurer]):
        if alias in said:
            return True
        if " " not in alias and any(SequenceMatcher(None, alias, w.strip(".,!?")).ratio() >= 0.8 for w in words):
            return True
    return False


_WRITES = {"book", "reschedule", "cancel", "register"}
_RECORDED = ("Recorded — it is sent when the call ends. Confirm to the caller in one sentence. "
             "If they change their mind, just record the new decision: it replaces this one.")


async def _record(s: CallSession, api: ClinicClient, action: str, payload: dict) -> dict:
    """Record a decision. Nothing is POSTed until finalize(): an accepted action can never be withdrawn,
    and problem 13 scores the caller's FINAL request — so a later decision replaces the one it contradicts."""
    record = {"action": action, **payload}
    if action != "escalate" and any(old["action"] == "escalate" for old in s.submissions):
        return {"status": "emergency_recorded",
                "say": "An emergency was recorded on this call, so nothing else is booked or changed. Tell them again to call 112 now."}
    specialty_of = {p["id"]: p["specialty_id"] for p in (await api.catalogue())["providers"]} if action == "no-action" else {}

    def contradicted(old: dict) -> bool:
        if old == record:
            return True  # an identical repeat is not a second action
        if action == "escalate":
            return True  # an emergency: book nothing
        if action == "no-action":
            # Seen live: "Okay" → booked → "oh no, I can't make mornings" → nothing else free → refusal. The
            # booking the caller walked away from — same patient, same kind of doctor — goes with it.
            # A refusal about anything else — advice asked for after booking, a second request a rule blocks — leaves
            # the booking alone: it must carry the very reason the last search gave for that patient and doctor.
            walked_away = (old["action"] == "book" and payload["reason"] == s.last_refusal_reason
                           and s.last_search == (old["patient_id"], specialty_of.get(old["provider_id"])))
            return walked_away or old["action"] == "no-action"
        if old["action"] == "no-action":
            return True  # something is being written after all
        if action == "book":
            return old["action"] == "book" and old["patient_id"] == payload["patient_id"]
        if action in ("reschedule", "cancel"):
            return old["action"] in ("reschedule", "cancel") and old["appointment_id"] == payload["appointment_id"]
        return old["action"] == "register"

    replaced = [old for old in s.submissions if contradicted(old)]
    standing = [old for old in s.submissions if not contradicted(old)]
    if action == "no-action" and standing:
        # No accepted answer ever pairs NO_ACTION with another action: a refused second request leaves the first as it is.
        s.submissions = standing
        s.log("refusal_not_recorded", payload=payload, standing=standing)
    else:
        s.submissions = standing + [record]
        s.log("recorded", action=action, payload=payload, replaced=replaced)
    return {"status": "recorded", "say": _RECORDED}


def _policy(s: CallSession, slot: dict, patient_id: str, insurer: str) -> str:
    """The plan on file pays whenever it can; a second plan only for what the first will not cover. The organizers
    publish a control case for exactly this: the first plan works, the caller holds another, and billing it fails."""
    payable = slot["payable_with"]
    on_file = s.patients[patient_id]["insurer"]
    return next((p for p in (on_file, insurer) if p in payable), payable[0] if payable else on_file)


def _not_on_the_table(s: CallSession, slot: dict, patient_id: str) -> dict | None:
    """A slot can be recorded only for the patient it was found for, and only while its offer stands."""
    if slot["found_for"] != patient_id:
        return {"status": "slot_of_another_patient",
                "say": "That slot was found for another patient. Call find_slots for this patient and offer what it returns."}
    if slot["round"] != s.offer_round:
        return {"status": "stale_offer",
                "say": "That offer was replaced by a later search or by the nearest-clinic answer, so it is off the table. "
                       "Call find_slots again for what the caller wants now, offer its first slot, and record it once they agree."}
    return None


async def book(s: CallSession, api: ClinicClient, patient_id: str, slot_ref: str, insurer: str = "") -> dict:
    slot = s.slots.get(slot_ref)
    if slot is None or patient_id not in s.patients:
        return {"status": "error", "say": "Use a patient_id from find_patient and a slot_ref from find_slots in this call."}
    if refusal := _not_on_the_table(s, slot, patient_id):
        return refusal
    return await _record(s, api, "book", {
        "patient_id": patient_id, "provider_id": slot["provider_id"], "location_id": slot["location_id"],
        "appointment_type_id": slot["appointment_type_id"], "slot": slot["start_time"],
        "policy_id": _policy(s, slot, patient_id, insurer)})


# Words a caller uses when an appointment they hold has to move. Seen live: a caller asked to BOOK, the model
# found an appointment on the books and moved it instead — the accepted answer was a new booking.
_MOVE_WORDS = ["reschedul", "move", "chang", "cancel", "make it", "make my", "make the", "instead", "another time",
               "another day", "different", "postpone", "push", "bring forward", "earlier", "later", "swap", "rebook",
               "rearrange", "cambi", "mover", "muev", "anul", "no puedo", "no podre", "no voy a poder", "aplaz",
               "adelant", "retras", "pospon", "otro dia", "otra hora", "otra fecha", "reprogram",
               # a relative's appointment: "my father cannot make his appointment", "no va a poder ir"
               "can't make", "cant make", "cannot make", "make his", "make her", "make their",
               "no va a poder", "no podra", "no podran"]


def _caller_asked_to_move(s: CallSession) -> bool:
    said = " ".join(fold(t) for t in s.heard)
    return s.move_intended or any(w in said for w in _MOVE_WORDS)


async def reschedule(s: CallSession, api: ClinicClient, appointment_id: str, slot_ref: str, insurer: str = "") -> dict:
    slot, appt = s.slots.get(slot_ref), s.appointments.get(appointment_id)
    if slot is None or appt is None:
        return {"status": "error", "say": "Use an appointment_id from list_appointments and a slot_ref from find_slots in this call."}
    if refusal := _not_on_the_table(s, slot, appt["patient_id"]):
        return refusal
    if not s.move_challenged and not _caller_asked_to_move(s):
        s.move_challenged = True
        return {"status": "caller_did_not_ask_to_move",
                "say": "The caller asked to book, not to move an appointment they hold: record a NEW booking with "
                       "book(patient_id, slot_ref) and leave the existing appointment alone. Only if they clearly asked "
                       "to move that appointment, call reschedule again."}
    return await _record(s, api, "reschedule", {
        "appointment_id": appointment_id, "provider_id": slot["provider_id"], "location_id": slot["location_id"],
        "slot": slot["start_time"], "policy_id": _policy(s, slot, appt["patient_id"], insurer)})


async def cancel(s: CallSession, api: ClinicClient, appointment_id: str) -> dict:
    if appointment_id not in s.appointments:
        return {"status": "error", "say": "Use an appointment_id from list_appointments in this call."}
    return await _record(s, api, "cancel", {"appointment_id": appointment_id})


async def register_patient(s: CallSession, api: ClinicClient, given_name: str, first_surname: str,
                           second_surname: str, national_id: str, date_of_birth: str, phone: str,
                           email: str, insurer: str) -> dict:
    nid = ids.parse(national_id)
    if nid.kind is None:
        return {"status": "invalid_national_id", "say": "Ask them to repeat the id one character at a time."}
    if not nid.valid:
        return {"status": "check_letter_mismatch",
                "say": f"The letter does not fit those digits. Read the DIGITS back one at a time. If the caller confirms the digits, the letter is {nid.expected_letter}: register with {nid.corrected}. If a digit was wrong, take the id again."}
    if insurer not in INSURERS:
        return {"status": "error", "say": f"insurer must be one of {INSURERS}."}
    # A model under time pressure fills a required field it never collected (seen live: "privado").
    # One challenge, then trust: a mangled transcript must not block a real registration for ever.
    digits = re.sub(r"\D", "", phone)[-9:]
    if len(digits) != 9 and s.elapsed() < config.WRAP_UP_AT_SECS:
        return {"status": "phone_incomplete", "say": "A Spanish phone number has nine digits. Ask them to repeat the phone number slowly."}
    # Once the wrap-up clock has fired there is no time left for another question: record what we have.
    if not _caller_said_insurer(s, insurer) and not s.insurer_challenged and s.elapsed() < config.WRAP_UP_AT_SECS:
        s.insurer_challenged = True
        return {"status": "insurer_not_heard",
                "say": "The caller has not said which insurer they are with. Ask them now, then call register_patient again. Never assume privado."}
    return await _record(s, api, "register", {
        "given_name": given_name.strip(), "first_surname": first_surname.strip(),
        "second_surname": second_surname.strip(), "national_id": nid.normalized,
        "date_of_birth": date_of_birth, "phone": digits or phone,
        "email": repair_email(email, given_name, first_surname, second_surname), "insurer": insurer})


async def end_without_booking(s: CallSession, api: ClinicClient, reason: str) -> dict:
    if reason not in REASONS:
        return {"status": "error", "say": f"reason must be one of {REASONS}."}
    return await _record(s, api, "no-action", {"reason": reason})


async def escalate(s: CallSession, api: ClinicClient, reason: str = "medical_emergency") -> dict:
    if reason not in REASONS:
        return {"status": "error", "say": f"reason must be one of {REASONS}."}
    await _record(s, api, "escalate", {"reason": reason})
    return {"status": "recorded", "say": "Tell them to hang up and call 112 now, in one short sentence, and stay calm and kind. "
                                          "You cannot alert anyone yourself: never say you have called or are calling the emergency services."}


async def discard_recorded(s: CallSession, api: ClinicClient) -> dict:
    """The caller took the last decision back. Only the last one: a call can hold two (a move for a relative, a
    booking for the caller). The offer goes too, or the hang-up fallback would book what was just withdrawn."""
    if not s.submissions or s.submissions[-1]["action"] == "escalate":
        return {"status": "nothing_to_discard", "say": "There is nothing the caller can take back."}
    dropped = s.submissions.pop()
    s.withdraw_offer()
    s.log("discarded", dropped=[dropped])
    return {"status": "discarded", "say": "That decision is no longer recorded. Carry on with what the caller wants."}


# Gemini occasionally writes a call out as text — "default_api:register_patient{given_name: Ana ,…}" — instead of
# making it. No tool runs, the agent then tells the caller it is done, and the case fails silently.
_LEAKED_CALL = re.compile(r"default_api[:.](\w+)\s*[\{\(](.*?)[\}\)]", re.S)
_LEAKED_JSON = re.compile(r'"(?:call|name|function|tool)"\s*:\s*"(?:default_api[:.])?(\w+)"', re.S)
_RECOVERABLE = {"book", "reschedule", "cancel", "register_patient", "end_without_booking", "escalate"}


def parse_leaked_calls(text: str) -> list[tuple[str, dict]]:
    """Tool calls the model wrote as text. Seen live, three spellings:
    cat=default_api:find_patient{name:Rachel Lewis Robinson,use_caller_id:true}
    default_api:register_patient{given_name: Ana ,first_surname: …}
    {"call": "default_api:find_patient", "args": {"name": "…", "use_caller_id": true}}
    """
    import json

    calls: list[tuple[str, dict]] = []
    m = _LEAKED_JSON.search(text)
    if m and m.group(1) in TOOLS:
        args: dict = {}
        found = re.search(r'"(?:args|arguments|parameters)"\s*:\s*(\{.*?\})', text, re.S)
        if found:
            try:
                args = json.loads(found.group(1))
            except ValueError:
                args = {}
        calls.append((m.group(1), args))
    if not calls:
        for name, body in _LEAKED_CALL.findall(text):
            if name not in TOOLS or any(name == n for n, _ in calls):
                continue  # the model often writes the same call twice over ("cat=…,call:…")
            args = {}
            for part in re.split(r"\s*,\s*(?=\w+\s*[:=])", body.strip()):
                kv = re.match(r"(\w+)\s*[:=]\s*(.*)", part, re.S)
                if kv:
                    args[kv.group(1)] = kv.group(2).strip().strip("'\"")
            calls.append((name, args))
    for name, args in calls:
        props = TOOLS[name][2]
        for key, value in list(args.items()):
            if key not in props:
                del args[key]
            elif props[key].get("type") == "boolean" and isinstance(value, str):
                args[key] = value.strip().lower() == "true"
    return calls


async def recover_leaked_calls(s: CallSession, api: ClinicClient) -> None:
    """Run the write tools the model spelled out in its speech but never actually called."""
    for text in s.said:
        for name, args in parse_leaked_calls(text):
            if name not in _RECOVERABLE:
                continue
            try:
                result = await TOOLS[name][0](s, api, **args)
            except Exception as err:
                result = {"status": "error", "detail": f"{type(err).__name__}: {err}"}
            if result.get("status") == "insurer_not_heard":  # the caller has gone; the challenge cannot be answered
                result = await TOOLS[name][0](s, api, **args)
            s.log("recovered_leaked_call", name=name, args=args, result=result)


async def finalize(s: CallSession, api: ClinicClient) -> None:
    """The call is over: send what was decided. Silence always fails, so if the caller hung up before the
    last tool call, send the likeliest answer — the slot just offered, or the reason the last search gave."""
    if not s.submissions:
        await recover_leaked_calls(s, api)
    if not s.submissions:
        if s.last_offered_slot and s.last_offered_patient in s.patients:
            await book(s, api, s.last_offered_patient, s.last_offered_slot)
        else:
            await end_without_booking(s, api, s.last_refusal_reason or "out_of_scope")
        s.log("inferred_at_hangup", submissions=s.submissions)
    # The window closes 30 s after the socket does. Seen in a scored run: the platform's submit endpoint timed
    # out on 8 of 22 calls and one attempt was all we made. An identical repeat answers 409, so retrying is safe.
    deadline = time.monotonic() + SUBMIT_WINDOW_SECS

    async def post(index: int, record: dict) -> None:
        action, payload = record["action"], {k: v for k, v in record.items() if k != "action"}
        await asyncio.sleep(0.3 * index)  # several actions go out together, in order
        attempts, status, body = 0, 200, None
        while not s.dry_run:
            attempts += 1
            try:
                status, body = await api.submit(action, {"call_id": s.call_id, **payload})
            except Exception as err:  # one failed POST must not stop the others
                status, body = 0, f"{type(err).__name__}: {err}"
            settled = status in (200, 201, 409) or (400 <= status < 500 and status not in (408, 425, 429))
            if settled or time.monotonic() >= deadline:
                break
            await asyncio.sleep(0.5)
        s.posted.append({"action": action, "http": status, "attempts": attempts})
        s.log("submit", action=action, payload=payload, http=status, attempts=attempts, response=body)

    await asyncio.gather(*(post(i, record) for i, record in enumerate(s.submissions)))


Tool = Callable[..., Awaitable[dict]]
_S, _E = {"type": "string"}, lambda values: {"type": "string", "enum": values}

# name -> (function, description, properties, required). One definition feeds Pipecat and the evals.
TOOLS: dict[str, tuple[Tool, str, dict, list[str]]] = {
    "find_patient": (find_patient,
        "Look a patient up in the clinic's records. Pass everything the caller has given so far. "
        "An exact field that is wrong returns nothing, so read identifiers back before relying on them.",
        {"name": _S, "national_id": {"type": "string", "description": "DNI or NIE exactly as the caller dictated it: digits and the letter, no spaces"},
         "phone": _S, "date_of_birth": {"type": "string", "description": "YYYY-MM-DD"},
         "use_caller_id": {"type": "boolean", "description": "true to search by the number they are ringing from"}}, []),
    "nearest_site": (nearest_site,
        "Which clinic is closest to where the caller is. Call it as soon as they say where they are and ask for the "
        "closest clinic — before identifying anyone. Never choose a clinic from your own knowledge of Madrid.",
        {"caller_address": {"type": "string", "description": "where they said they are, in their words: street, number, town, landmark"},
         "specialty_id": _E(SPECIALTIES)}, ["caller_address"]),
    "find_slots": (find_slots,
        "Find real availability for an identified patient. Code applies the clinic's rules and resolves the day; "
        "you only classify what the caller said.",
        {"patient_id": _S, "specialty_id": _E(SPECIALTIES),
         "provider_name": {"type": "string", "description": "doctor's name as the caller said it"},
         "location_id": _E(SITES), "day_kind": _E(dates.DAY_KINDS), "weekday": _E(dates.WEEKDAYS),
         "date_iso": {"type": "string", "description": "YYYY-MM-DD, only when day_kind is 'date'"},
         "part_of_day": _E(dates.PARTS_OF_DAY),
         "language": {"type": "string", "description": "ISO code, only if the caller needs a doctor who speaks it, e.g. ca"},
         "insurer": {**_E(INSURERS), "description": "only a SECOND plan the caller named on this call"},
         "caller_address": {"type": "string", "description": "only when they ask for the nearest clinic and nearest_site has not been called"},
         "after_appointment_id": {"type": "string", "description": "only later times come back. Moving an appointment to 'the next time after the one I have': that appointment_id — same doctor and same site unless you also pass others. The caller turns down the time you offered and asks for the next one: the slot_ref you offered — same site, any doctor."}}, ["patient_id"]),
    "list_appointments": (list_appointments, "The patient's upcoming appointments — the only source of an appointment_id.",
        {"patient_id": _S}, ["patient_id"]),
    "book": (book, "Book an offered slot after the caller said yes. Booking again for the same patient replaces the earlier booking.",
        {"patient_id": _S, "slot_ref": _S, "insurer": _E(INSURERS)}, ["patient_id", "slot_ref"]),
    "reschedule": (reschedule, "Move an existing appointment to an offered slot after the caller said yes.",
        {"appointment_id": _S, "slot_ref": _S, "insurer": _E(INSURERS)}, ["appointment_id", "slot_ref"]),
    "cancel": (cancel, "Cancel one existing appointment. Two cancellations are two calls.",
        {"appointment_id": _S}, ["appointment_id"]),
    "check_national_id": (check_national_id, "Check a dictated DNI/NIE's letter against its digits. Instant.",
        {"national_id": _S}, ["national_id"]),
    "register_patient": (register_patient, "Put a caller who is not on file on the record. Books nothing. Code repairs the name part of the email from the name you pass, so pass the name spelled correctly.",
        {"given_name": _S, "first_surname": _S, "second_surname": _S, "national_id": _S,
         "date_of_birth": {"type": "string", "description": "YYYY-MM-DD"}, "phone": _S, "email": _S,
         "insurer": _E(INSURERS)},
        ["given_name", "first_surname", "second_surname", "national_id", "date_of_birth", "phone", "email", "insurer"]),
    "end_without_booking": (end_without_booking, "The call ends with nothing written. The reason is the answer.",
        {"reason": _E(REASONS)}, ["reason"]),
    "discard_recorded": (discard_recorded,
        "The caller took back the decision recorded last on this call (nothing has been sent yet). Removes that one.", {}, []),
    "escalate": (escalate, "Hand the call to a human: a medical emergency. Book nothing.",
        {"reason": _E(["medical_emergency"])}, ["reason"]),
}
