"""
Phase 69 — Contract tests for booking_amended skill.

Verifies:
1. Full amendment payload (all fields) → BOOKING_AMENDED emitted with all fields
2. Partial amendment — only new_check_in → COALESCE-safe (missing fields NOT in payload)
3. Partial amendment — only new_check_out → same
4. Partial amendment — only guest_count → same
5. Minimal amendment — booking_id only → BOOKING_AMENDED with just booking_id
6. booking_id fallback construction when adapter omits it
7. Emitted event type is exactly "BOOKING_AMENDED"
8. Skill name is "OTA_BOOKING_AMENDED"
9. No state_upserts produced
10. amendment_reason included when present
11. amendment_reason excluded when None
12. guest_count excluded when None
13. dates excluded when None
14. booking_id always present in emitted payload
15. Empty booking_id fallback uses provider+reservation_id
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helper: run the skill
# ---------------------------------------------------------------------------

def _run(payload: dict) -> "SkillOutput":  # type: ignore[name-defined]
    from core.skills.booking_amended.skill import run
    return run(payload)


# ---------------------------------------------------------------------------
# 1. Full amendment
# ---------------------------------------------------------------------------

class TestFullAmendment:

    def test_full_amendment_emits_booking_amended(self) -> None:
        result = _run({
            "booking_id": "bookingcom_res123",
            "new_check_in": "2026-10-01",
            "new_check_out": "2026-10-05",
            "new_guest_count": 3,
            "amendment_reason": "guest request",
            "provider": "bookingcom",
            "reservation_id": "res123",
        })
        assert len(result.events_to_emit) == 1
        ev = result.events_to_emit[0]
        assert ev.type == "BOOKING_AMENDED"

    def test_full_amendment_payload_contains_all_amended_fields(self) -> None:
        result = _run({
            "booking_id": "bookingcom_res123",
            "new_check_in": "2026-10-01",
            "new_check_out": "2026-10-05",
            "new_guest_count": 3,
            "amendment_reason": "guest request",
        })
        p = result.events_to_emit[0].payload
        assert p["booking_id"] == "bookingcom_res123"
        assert p["new_check_in"] == "2026-10-01"
        assert p["new_check_out"] == "2026-10-05"
        assert p["new_guest_count"] == 3
        assert p["amendment_reason"] == "guest request"


# ---------------------------------------------------------------------------
# 2–4. Partial amendments — only changed fields forwarded
# ---------------------------------------------------------------------------

class TestPartialAmendment:

    def test_check_in_only_no_check_out_in_payload(self) -> None:
        result = _run({
            "booking_id": "expedia_exp001",
            "new_check_in": "2026-11-01",
            "new_check_out": None,
        })
        p = result.events_to_emit[0].payload
        assert "new_check_in" in p
        assert p["new_check_in"] == "2026-11-01"
        assert "new_check_out" not in p   # COALESCE — do not overwrite existing

    def test_check_out_only_no_check_in_in_payload(self) -> None:
        result = _run({
            "booking_id": "airbnb_hm999",
            "new_check_in": None,
            "new_check_out": "2026-11-10",
        })
        p = result.events_to_emit[0].payload
        assert "new_check_out" in p
        assert p["new_check_out"] == "2026-11-10"
        assert "new_check_in" not in p

    def test_guest_count_only(self) -> None:
        result = _run({
            "booking_id": "agoda_9876",
            "new_guest_count": 4,
        })
        p = result.events_to_emit[0].payload
        assert p["new_guest_count"] == 4
        assert "new_check_in" not in p
        assert "new_check_out" not in p

    def test_amendment_reason_only_no_dates_no_count(self) -> None:
        result = _run({
            "booking_id": "tripcom_order999",
            "amendment_reason": "corporate relocation",
        })
        p = result.events_to_emit[0].payload
        assert p["amendment_reason"] == "corporate relocation"
        assert "new_check_in" not in p
        assert "new_check_out" not in p
        assert "new_guest_count" not in p


# ---------------------------------------------------------------------------
# 5. Minimal — booking_id only
# ---------------------------------------------------------------------------

class TestMinimalPayload:

    def test_minimal_payload_booking_id_only(self) -> None:
        result = _run({"booking_id": "bookingcom_res001"})
        p = result.events_to_emit[0].payload
        assert p == {"booking_id": "bookingcom_res001"}

    def test_booking_id_always_present(self) -> None:
        result = _run({"booking_id": "expedia_abc", "new_check_in": "2026-12-01"})
        assert "booking_id" in result.events_to_emit[0].payload


# ---------------------------------------------------------------------------
# 6. booking_id fallback
# ---------------------------------------------------------------------------

class TestBookingIdFallback:

    def test_fallback_builds_from_provider_and_reservation_id(self) -> None:
        result = _run({
            "provider": "bookingcom",
            "reservation_id": "res777",
            "new_check_in": "2026-09-01",
        })
        p = result.events_to_emit[0].payload
        assert p["booking_id"] == "bookingcom_res777"

    def test_fallback_uses_reservation_id_when_no_provider(self) -> None:
        result = _run({
            "reservation_id": "fallback_ref",
        })
        p = result.events_to_emit[0].payload
        assert p["booking_id"] == "fallback_ref"

    def test_explicit_booking_id_takes_precedence_over_fallback(self) -> None:
        result = _run({
            "booking_id": "explicit_id",
            "provider": "airbnb",
            "reservation_id": "should_be_ignored",
        })
        p = result.events_to_emit[0].payload
        assert p["booking_id"] == "explicit_id"


# ---------------------------------------------------------------------------
# 7–9. Skill contract compliance
# ---------------------------------------------------------------------------

class TestSkillContract:

    def test_reason_is_ota_booking_amended(self) -> None:
        result = _run({"booking_id": "bookingcom_x"})
        assert result.reason == "OTA_BOOKING_AMENDED"

    def test_no_state_upserts(self) -> None:
        result = _run({"booking_id": "bookingcom_x"})
        assert result.state_upserts == []

    def test_exactly_one_emitted_event(self) -> None:
        result = _run({"booking_id": "bookingcom_x"})
        assert len(result.events_to_emit) == 1

    def test_emitted_type_is_booking_amended(self) -> None:
        result = _run({"booking_id": "bookingcom_x"})
        assert result.events_to_emit[0].type == "BOOKING_AMENDED"

    def test_apply_result_is_applied(self) -> None:
        result = _run({"booking_id": "bookingcom_x"})
        assert result.apply_result == "APPLIED"


# ---------------------------------------------------------------------------
# 10–11. None field exclusion
# ---------------------------------------------------------------------------

class TestNoneExclusion:

    def test_guest_count_none_excluded(self) -> None:
        result = _run({"booking_id": "b_x", "new_guest_count": None})
        assert "new_guest_count" not in result.events_to_emit[0].payload

    def test_amendment_reason_none_excluded(self) -> None:
        result = _run({"booking_id": "b_x", "amendment_reason": None})
        assert "amendment_reason" not in result.events_to_emit[0].payload

    def test_check_in_none_excluded(self) -> None:
        result = _run({"booking_id": "b_x", "new_check_in": None})
        assert "new_check_in" not in result.events_to_emit[0].payload

    def test_check_out_none_excluded(self) -> None:
        result = _run({"booking_id": "b_x", "new_check_out": None})
        assert "new_check_out" not in result.events_to_emit[0].payload
