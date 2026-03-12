"""
Phase 333 — Booking.com Content Adapter Integration Tests
==========================================================

First-ever tests for `adapters/outbound/bookingcom_content.py`.

Group A: build_content_payload — Required Field Validation
  ✓  Valid payload builds successfully
  ✓  Missing bcom_hotel_id → ValueError
  ✓  Missing name → ValueError
  ✓  Missing address → ValueError
  ✓  Invalid country_code (not 2 chars) → ValueError
  ✓  Invalid cancellation_policy_code → ValueError

Group B: build_content_payload — Payload Shape and Content
  ✓  hotel_id is always string
  ✓  country_code is uppercased
  ✓  Description truncated at 2000 chars
  ✓  Optional fields included when provided (star_rating, amenities, photos)
  ✓  Optional timing fields included (check_in_time, check_out_time)
  ✓  Default cancellation code is MODERATE when not specified

Group C: list_pushed_fields
  ✓  Returns sorted list of payload keys
  ✓  Optional fields appear when in payload

Group D: PushResult Shape
  ✓  dry_run=True field preserved
  ✓  success=False with error preserved

CI-safe: pure function tests, no DB, no network.
"""
from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("IHOUSE_DEV_MODE", "true")
os.environ.setdefault("IHOUSE_ENV", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from adapters.outbound.bookingcom_content import (
    PushResult,
    build_content_payload,
    list_pushed_fields,
    _MAX_DESCRIPTION_CHARS,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _base_meta(**overrides) -> dict:
    base = {
        "property_id": "P-001",
        "bcom_hotel_id": "1234567",
        "name": "Sunset Villa",
        "address": "123 Beach Road",
        "city": "Bangkok",
        "country_code": "TH",
        "cancellation_policy_code": "FLEX",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — Required Field Validation
# ---------------------------------------------------------------------------

class TestRequiredFieldValidation:

    def test_valid_payload_builds(self):
        payload = build_content_payload(_base_meta())
        assert payload["hotel_id"] == "1234567"
        assert payload["name"] == "Sunset Villa"

    def test_missing_hotel_id_raises(self):
        meta = _base_meta()
        del meta["bcom_hotel_id"]
        # Also remove external_id fallback
        with pytest.raises(ValueError, match="bcom_hotel_id"):
            build_content_payload(meta)

    def test_missing_name_raises(self):
        meta = _base_meta(name=None)
        with pytest.raises(ValueError, match="name"):
            build_content_payload(meta)

    def test_missing_address_raises(self):
        meta = _base_meta(address=None)
        with pytest.raises(ValueError):
            build_content_payload(meta)

    def test_invalid_country_code_raises(self):
        meta = _base_meta(country_code="THAI")  # not 2 chars
        with pytest.raises(ValueError, match="country_code"):
            build_content_payload(meta)

    def test_invalid_cancellation_code_raises(self):
        meta = _base_meta(cancellation_policy_code="UNKNOWN")
        with pytest.raises(ValueError, match="cancellation_policy_code"):
            build_content_payload(meta)


# ---------------------------------------------------------------------------
# Group B — Payload Shape and Content
# ---------------------------------------------------------------------------

class TestPayloadShape:

    def test_hotel_id_is_string(self):
        meta = _base_meta(bcom_hotel_id=9999999)  # int input
        payload = build_content_payload(meta)
        assert isinstance(payload["hotel_id"], str)
        assert payload["hotel_id"] == "9999999"

    def test_country_code_uppercased(self):
        meta = _base_meta(country_code="th")
        payload = build_content_payload(meta)
        assert payload["country_code"] == "TH"

    def test_description_truncated_at_limit(self):
        long_desc = "x" * (_MAX_DESCRIPTION_CHARS + 100)
        meta = _base_meta(description=long_desc)
        payload = build_content_payload(meta)
        assert len(payload["description"]) == _MAX_DESCRIPTION_CHARS

    def test_short_description_not_truncated(self):
        meta = _base_meta(description="Short description.")
        payload = build_content_payload(meta)
        assert payload["description"] == "Short description."

    def test_optional_star_rating_included(self):
        meta = _base_meta(star_rating=4)
        payload = build_content_payload(meta)
        assert payload["star_rating"] == 4

    def test_optional_amenities_included(self):
        meta = _base_meta(amenities=[1, 5, 99])
        payload = build_content_payload(meta)
        assert payload["amenities"] == [1, 5, 99]

    def test_optional_photos_included(self):
        urls = ["https://cdn.example.com/photo1.jpg"]
        meta = _base_meta(photos=urls)
        payload = build_content_payload(meta)
        assert payload["photos"] == urls

    def test_optional_timezone_fields(self):
        meta = _base_meta(check_in_time="15:00", check_out_time="11:00")
        payload = build_content_payload(meta)
        assert payload["check_in_time"] == "15:00"
        assert payload["check_out_time"] == "11:00"

    def test_default_cancellation_is_moderate(self):
        meta = _base_meta()
        del meta["cancellation_policy_code"]
        payload = build_content_payload(meta)
        assert payload["cancellation_policy_code"] == "MODERATE"


# ---------------------------------------------------------------------------
# Group C — list_pushed_fields
# ---------------------------------------------------------------------------

class TestListPushedFields:

    def test_returns_sorted_keys(self):
        payload = build_content_payload(_base_meta())
        fields = list_pushed_fields(payload)
        assert fields == sorted(fields)

    def test_optional_fields_appear(self):
        meta = _base_meta(star_rating=3, amenities=[1, 2])
        payload = build_content_payload(meta)
        fields = list_pushed_fields(payload)
        assert "star_rating" in fields
        assert "amenities" in fields


# ---------------------------------------------------------------------------
# Group D — PushResult Shape
# ---------------------------------------------------------------------------

class TestPushResultShape:

    def test_dry_run_flag_preserved(self):
        result = PushResult(
            property_id="P-001", bcom_hotel_id="H-123",
            success=True, dry_run=True, fields_pushed=["name", "address"]
        )
        assert result.dry_run is True

    def test_failure_with_error_message(self):
        result = PushResult(
            property_id="P-001", bcom_hotel_id=None,
            success=False, error="Validation failed: missing name",
        )
        assert result.success is False
        assert "name" in result.error
