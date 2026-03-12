"""
Phase 328 — Guest Messaging Copilot Integration Tests
======================================================

First-ever tests for `api/guest_messaging_copilot.py`.

Group A: Heuristic Draft Content
  ✓  check_in_instructions includes property name + access code
  ✓  booking_confirmation includes check-in + check-out
  ✓  pre_arrival_info includes check-in date
  ✓  check_out_reminder includes check-out time
  ✓  issue_apology contains apology language
  ✓  custom intent uses custom_prompt text

Group B: Language + Salutation
  ✓  English salutation format
  ✓  Thai salutation format
  ✓  Japanese salutation format
  ✓  Unknown language fallback to English

Group C: Tone Variations
  ✓  friendly closing differs from professional
  ✓  brief closing is present in draft

Group D: Subject Generation
  ✓  Each intent returns unique subject
  ✓  Property name embedded in subject
  ✓  Pre-arrival includes check-in date in subject

Group E: Total Nights Calculation
  ✓  5-night stay shows "5 nights"
  ✓  1-night stay shows "1 night" (not "1 nights")
  ✓  Missing dates → "your stay" fallback

CI-safe: pure function tests, no DB, no network.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from api.guest_messaging_copilot import (
    _build_heuristic_draft,
    _build_subject,
)


# ---------------------------------------------------------------------------
# Context builder helper
# ---------------------------------------------------------------------------

def _ctx(
    guest_name: str = "Alice",
    property_name: str = "Sunset Villa",
    check_in: str = "2026-04-01",
    check_out: str = "2026-04-06",
    checkin_time: str = "15:00",
    checkout_time: str = "11:00",
    wifi: str = "sunshine123",
    access_code: str = "4567",
    total_nights: int = 5,
) -> dict:
    return {
        "guest_name": guest_name,
        "property_name": property_name,
        "check_in": check_in,
        "check_out": check_out,
        "property_checkin_time": checkin_time,
        "property_checkout_time": checkout_time,
        "property_wifi": wifi,
        "property_access_code": access_code,
        "total_nights": total_nights,
    }


# ---------------------------------------------------------------------------
# Group A — Heuristic Draft Content
# ---------------------------------------------------------------------------

class TestHeuristicDraftContent:

    def test_check_in_includes_property_and_access_code(self):
        draft = _build_heuristic_draft(
            "check_in_instructions", _ctx(), "en", "friendly", None
        )
        assert "Sunset Villa" in draft
        assert "4567" in draft

    def test_booking_confirmation_includes_dates(self):
        draft = _build_heuristic_draft(
            "booking_confirmation", _ctx(), "en", "friendly", None
        )
        assert "2026-04-01" in draft
        assert "2026-04-06" in draft

    def test_pre_arrival_includes_checkin_date(self):
        draft = _build_heuristic_draft(
            "pre_arrival_info", _ctx(), "en", "friendly", None
        )
        assert "2026-04-01" in draft

    def test_check_out_includes_checkout_time(self):
        draft = _build_heuristic_draft(
            "check_out_reminder", _ctx(), "en", "friendly", None
        )
        assert "11:00" in draft

    def test_apology_contains_apology_language(self):
        draft = _build_heuristic_draft(
            "issue_apology", _ctx(), "en", "friendly", None
        )
        lower = draft.lower()
        assert "apologise" in lower or "apology" in lower or "sorry" in lower

    def test_custom_uses_custom_prompt(self):
        prompt = "Please note that the pool will be closed for maintenance on your arrival day."
        draft = _build_heuristic_draft(
            "custom", _ctx(), "en", "friendly", prompt
        )
        assert prompt in draft


# ---------------------------------------------------------------------------
# Group B — Language + Salutation
# ---------------------------------------------------------------------------

class TestLanguageAndSalutation:

    def test_english_salutation(self):
        draft = _build_heuristic_draft(
            "check_in_instructions", _ctx(), "en", "friendly", None
        )
        assert "Dear Alice" in draft

    def test_thai_salutation(self):
        draft = _build_heuristic_draft(
            "check_in_instructions", _ctx(), "th", "friendly", None
        )
        assert "Alice" in draft  # guest name always present
        assert "เรียน" in draft

    def test_japanese_salutation(self):
        draft = _build_heuristic_draft(
            "check_in_instructions", _ctx(guest_name="田中"), "ja", "friendly", None
        )
        assert "様" in draft

    def test_unknown_language_falls_back_to_english(self):
        draft = _build_heuristic_draft(
            "check_in_instructions", _ctx(), "fr", "friendly", None
        )
        assert "Dear Alice" in draft  # en salutation


# ---------------------------------------------------------------------------
# Group C — Tone Variations
# ---------------------------------------------------------------------------

class TestToneVariations:

    def test_friendly_closing_differs_from_professional(self):
        friendly = _build_heuristic_draft(
            "booking_confirmation", _ctx(), "en", "friendly", None
        )
        professional = _build_heuristic_draft(
            "booking_confirmation", _ctx(), "en", "professional", None
        )
        # Closing text is different
        assert friendly != professional

    def test_brief_closing_present(self):
        draft = _build_heuristic_draft(
            "booking_confirmation", _ctx(), "en", "brief", None
        )
        assert "Thanks" in draft or "Host" in draft


# ---------------------------------------------------------------------------
# Group D — Subject Generation
# ---------------------------------------------------------------------------

class TestSubjectGeneration:

    def test_all_intents_produce_distinct_subjects(self):
        intents = [
            "check_in_instructions",
            "booking_confirmation",
            "pre_arrival_info",
            "check_out_reminder",
            "issue_apology",
            "custom",
        ]
        subjects = {_build_subject(i, _ctx(), "en") for i in intents}
        assert len(subjects) == len(intents)

    def test_property_name_in_subject(self):
        subject = _build_subject("check_in_instructions", _ctx(), "en")
        assert "Sunset Villa" in subject

    def test_pre_arrival_includes_checkin_in_subject(self):
        subject = _build_subject("pre_arrival_info", _ctx(), "en")
        assert "2026-04-01" in subject


# ---------------------------------------------------------------------------
# Group E — Nights Calculation
# ---------------------------------------------------------------------------

class TestNightsCalculation:

    def test_five_night_stay(self):
        draft = _build_heuristic_draft(
            "booking_confirmation",
            _ctx(check_in="2026-04-01", check_out="2026-04-06", total_nights=5),
            "en", "friendly", None,
        )
        assert "5 nights" in draft

    def test_single_night_no_plural(self):
        draft = _build_heuristic_draft(
            "booking_confirmation",
            _ctx(check_in="2026-04-01", check_out="2026-04-02", total_nights=1),
            "en", "friendly", None,
        )
        assert "1 night" in draft
        assert "1 nights" not in draft

    def test_missing_dates_fallback(self):
        ctx = _ctx()
        ctx["total_nights"] = None
        ctx["check_in"] = None
        ctx["check_out"] = None
        draft = _build_heuristic_draft(
            "booking_confirmation", ctx, "en", "friendly", None
        )
        assert "your stay" in draft
