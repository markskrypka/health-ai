"""Tests for the jury defense behaviors and judge edge cases."""

import json
from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest

from clinic_agent import config, dates, ids, prompt, tools
from clinic_agent.clinic import ClinicClient
from clinic_agent.config import MADRID
from clinic_agent.session import CallSession


def test_jury_mode_config_defaults():
    assert config.JURY_MODE is True
    assert config.SHOW_CHART_NOTES is True


def test_prompt_build_includes_jury_mode_and_defenses():
    cat = json.loads((config.ORGANIZERS_DIR / "clinic.json").read_text())
    now = datetime(2026, 9, 21, 10, 0, tzinfo=MADRID)
    system_prompt = prompt.build(cat, now, has_caller_id=True)

    # Check key defense instructions in the prompt
    assert "JURY DEMO MODE" in system_prompt
    assert "Unusual, foreign or phonetically ambiguous names" in system_prompt
    assert "Near-miss doctor names that sound alike" in system_prompt
    assert "Sáez" in system_prompt and "Sáenz" in system_prompt
    assert "Don Álvaro Cid" in system_prompt
    assert "out_of_scope" in system_prompt
    assert "medical_emergency" in system_prompt
    assert "Fiesta Nacional" in system_prompt


def test_doctor_homophones_resolution():
    cat = json.loads((config.ORGANIZERS_DIR / "clinic.json").read_text())

    # Sáez vs Sáenz
    saez_matches = tools._resolve_provider(cat, "Sáez", None)
    names = {p["name"] for p in saez_matches}
    assert any("Sáez" in n for n in names)
    assert any("Sáenz" in n for n in names)

    # Iglesias vs Iglesia
    iglesias_matches = tools._resolve_provider(cat, "Iglesias", None)
    iglesias_names = {p["name"] for p in iglesias_matches}
    assert any("Iglesias" in n for n in iglesias_names)
    assert any("Iglesia" in n for n in iglesias_names)


@pytest.mark.asyncio
async def test_find_slots_ambiguous_provider_returns_descriptive_say():
    cat = json.loads((config.ORGANIZERS_DIR / "clinic.json").read_text())
    api = ClinicClient()
    api.catalogue = AsyncMock(return_value=cat)

    session = CallSession(call_id="test_homophone", now=datetime(2026, 9, 21, 9, 0, tzinfo=MADRID))
    session.patients["P00001"] = {"patient_id": "P00001"}

    res = await tools.find_slots(session, api, patient_id="P00001", provider_name="Sáez")
    assert res["status"] == "ambiguous_provider"
    assert "specialty" in res["say"].lower()
    assert len(res["options"]) >= 2


@pytest.mark.asyncio
async def test_escalate_medical_emergency_records_correctly():
    api = ClinicClient()
    session = CallSession(call_id="test_escalate", now=datetime(2026, 9, 21, 9, 0, tzinfo=MADRID))

    res = await tools.escalate(session, api, reason="medical_emergency")
    assert res["status"] == "recorded"
    assert len(session.submissions) == 1
    assert session.submissions[0]["action"] == "escalate"
    assert session.submissions[0]["reason"] == "medical_emergency"


@pytest.mark.asyncio
async def test_end_without_booking_out_of_scope():
    api = ClinicClient()
    session = CallSession(call_id="test_out_of_scope", now=datetime(2026, 9, 21, 9, 0, tzinfo=MADRID))

    res = await tools.end_without_booking(session, api, reason="out_of_scope")
    assert res["status"] == "recorded"
    assert len(session.submissions) == 1
    assert session.submissions[0]["action"] == "no-action"
    assert session.submissions[0]["reason"] == "out_of_scope"


def test_repair_email_handles_unusual_and_compound_names():
    # Compound / unusual foreign name email where STT mangled Picard -> Picar
    repaired = tools.repair_email("jeanluc.picar99@gmail.com", "Jean-Luc", "Picard", "")
    assert "@gmail." in repaired
    assert "picard" in repaired

    # Spanish compound name where STT wrote Sanches instead of Sánchez
    repaired_es = tools.repair_email("maria_carmen_sanches12@hotmail.com", "María del Carmen", "Sánchez", "Gómez")
    assert "@hotmail." in repaired_es
    assert "sanchez" in repaired_es
