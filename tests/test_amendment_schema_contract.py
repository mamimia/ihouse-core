"""
Phase 49 — Contract tests for Normalized AmendmentPayload Schema.

Verifies that:
1. AmendmentFields is a frozen dataclass with correct fields
2. Booking.com extractor maps new_reservation_info correctly
3. Expedia extractor maps changes.dates correctly
4. Missing fields return None (no raise)
5. Guest count is coerced to int
6. Unknown provider raises ValueError
7. normalize_amendment dispatches to correct extractor
8. Empty string fields return None
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest


# ---------------------------------------------------------------------------
# AmendmentFields schema
# ---------------------------------------------------------------------------

class TestAmendmentFieldsSchema:

    def test_is_frozen_dataclass(self) -> None:
        from adapters.ota.schemas import AmendmentFields
        af = AmendmentFields(
            new_check_in="2026-09-01",
            new_check_out="2026-09-05",
            new_guest_count=2,
            amendment_reason="guest request",
        )
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            af.new_check_in = "2026-10-01"  # type: ignore[misc]

    def test_all_optional_fields_can_be_none(self) -> None:
        from adapters.ota.schemas import AmendmentFields
        af = AmendmentFields(
            new_check_in=None,
            new_check_out=None,
            new_guest_count=None,
            amendment_reason=None,
        )
        assert af.new_check_in is None
        assert af.new_check_out is None
        assert af.new_guest_count is None
        assert af.amendment_reason is None


# ---------------------------------------------------------------------------
# Booking.com extractor
# ---------------------------------------------------------------------------

class TestBookingComExtractor:

    def test_full_payload_extracted_correctly(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_bookingcom
        payload = {
            "new_reservation_info": {
                "arrival_date": "2026-09-01",
                "departure_date": "2026-09-05",
                "number_of_guests": 3,
                "modification_reason": "room upgrade",
            }
        }
        result = extract_amendment_bookingcom(payload)
        assert result.new_check_in == "2026-09-01"
        assert result.new_check_out == "2026-09-05"
        assert result.new_guest_count == 3
        assert result.amendment_reason == "room upgrade"

    def test_missing_new_reservation_info_returns_all_none(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_bookingcom
        result = extract_amendment_bookingcom({})
        assert result.new_check_in is None
        assert result.new_check_out is None
        assert result.new_guest_count is None
        assert result.amendment_reason is None

    def test_partial_payload_missing_dates(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_bookingcom
        payload = {
            "new_reservation_info": {
                "number_of_guests": 2,
            }
        }
        result = extract_amendment_bookingcom(payload)
        assert result.new_check_in is None
        assert result.new_check_out is None
        assert result.new_guest_count == 2

    def test_empty_string_field_returns_none(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_bookingcom
        payload = {
            "new_reservation_info": {
                "arrival_date": "",
                "modification_reason": "  ",
            }
        }
        result = extract_amendment_bookingcom(payload)
        assert result.new_check_in is None
        assert result.amendment_reason is None

    def test_guest_count_string_coerced_to_int(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_bookingcom
        payload = {
            "new_reservation_info": {"number_of_guests": "4"}
        }
        result = extract_amendment_bookingcom(payload)
        assert result.new_guest_count == 4
        assert isinstance(result.new_guest_count, int)


# ---------------------------------------------------------------------------
# Expedia extractor
# ---------------------------------------------------------------------------

class TestExpediaExtractor:

    def test_full_payload_extracted_correctly(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_expedia
        payload = {
            "changes": {
                "dates": {
                    "check_in": "2026-09-01",
                    "check_out": "2026-09-07",
                },
                "guests": {"count": 5},
                "reason": "family expansion",
            }
        }
        result = extract_amendment_expedia(payload)
        assert result.new_check_in == "2026-09-01"
        assert result.new_check_out == "2026-09-07"
        assert result.new_guest_count == 5
        assert result.amendment_reason == "family expansion"

    def test_missing_changes_returns_all_none(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_expedia
        result = extract_amendment_expedia({})
        assert result.new_check_in is None
        assert result.new_guest_count is None

    def test_partial_payload_no_guests(self) -> None:
        from adapters.ota.amendment_extractor import extract_amendment_expedia
        payload = {
            "changes": {
                "dates": {"check_in": "2026-09-02", "check_out": "2026-09-06"}
            }
        }
        result = extract_amendment_expedia(payload)
        assert result.new_check_in == "2026-09-02"
        assert result.new_guest_count is None


# ---------------------------------------------------------------------------
# normalize_amendment dispatcher
# ---------------------------------------------------------------------------

class TestNormalizeAmendmentDispatcher:

    def test_bookingcom_dispatches_to_bookingcom_extractor(self) -> None:
        from adapters.ota.amendment_extractor import normalize_amendment
        payload = {
            "new_reservation_info": {"arrival_date": "2026-10-01", "departure_date": "2026-10-05"}
        }
        result = normalize_amendment("bookingcom", payload)
        assert result.new_check_in == "2026-10-01"

    def test_expedia_dispatches_to_expedia_extractor(self) -> None:
        from adapters.ota.amendment_extractor import normalize_amendment
        payload = {
            "changes": {"dates": {"check_in": "2026-11-01", "check_out": "2026-11-07"}}
        }
        result = normalize_amendment("expedia", payload)
        assert result.new_check_in == "2026-11-01"

    def test_unknown_provider_raises_value_error(self) -> None:
        from adapters.ota.amendment_extractor import normalize_amendment
        with pytest.raises(ValueError, match="Unknown provider"):
            normalize_amendment("airbnb", {})

    def test_provider_is_case_insensitive(self) -> None:
        from adapters.ota.amendment_extractor import normalize_amendment
        payload = {
            "new_reservation_info": {"arrival_date": "2026-10-01", "departure_date": "2026-10-03"}
        }
        result = normalize_amendment("BookingCom", payload)
        assert result.new_check_in == "2026-10-01"

    def test_returns_amendment_fields_type(self) -> None:
        from adapters.ota.amendment_extractor import normalize_amendment
        from adapters.ota.schemas import AmendmentFields
        result = normalize_amendment("expedia", {})
        assert isinstance(result, AmendmentFields)
