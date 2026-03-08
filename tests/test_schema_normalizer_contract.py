"""
test_schema_normalizer_contract.py — Phase 77

Contract tests for schema_normalizer.normalize_schema().

Groups:
  A — canonical_guest_count per provider (5 tests)
  B — canonical_booking_ref per provider (5 tests)
  C — canonical_property_id per provider (5 tests)
  D — original raw fields are preserved after normalization (5 tests)
  E — missing fields yield None, no KeyError (5 tests)
"""

import pytest
from adapters.ota.schema_normalizer import normalize_schema


# ---------------------------------------------------------------------------
# Helpers — minimal payloads per provider
# ---------------------------------------------------------------------------

def _bookingcom_payload(**overrides):
    base = {
        "tenant_id": "t1",
        "event_id": "ev-bc-1",
        "reservation_id": "RES-001",
        "property_id": "PROP-BC-1",
        "occurred_at": "2026-01-01T10:00:00",
        "number_of_guests": 2,
    }
    base.update(overrides)
    return base


def _airbnb_payload(**overrides):
    base = {
        "tenant_id": "t1",
        "event_id": "ev-ab-1",
        "reservation_id": "AB-001",
        "listing_id": "LISTING-1",
        "occurred_at": "2026-01-01T10:00:00",
        "guest_count": 3,
    }
    base.update(overrides)
    return base


def _expedia_payload(**overrides):
    base = {
        "tenant_id": "t1",
        "event_id": "ev-ex-1",
        "reservation_id": "EX-001",
        "property_id": "PROP-EX-1",
        "occurred_at": "2026-01-01T10:00:00",
        "guests": {"count": 4},
    }
    base.update(overrides)
    return base


def _agoda_payload(**overrides):
    base = {
        "tenant_id": "t1",
        "event_id": "ev-ag-1",
        "booking_ref": "AGD-001",
        "property_id": "PROP-AG-1",
        "occurred_at": "2026-01-01T10:00:00",
        "num_guests": 1,
    }
    base.update(overrides)
    return base


def _tripcom_payload(**overrides):
    base = {
        "tenant_id": "t1",
        "event_id": "ev-tc-1",
        "order_id": "TC-001",
        "hotel_id": "HOTEL-1",
        "occurred_at": "2026-01-01T10:00:00",
        "guests": 5,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — canonical_guest_count
# ---------------------------------------------------------------------------

class TestCanonicalGuestCount:

    def test_bookingcom_guest_count(self):
        result = normalize_schema("bookingcom", _bookingcom_payload(number_of_guests=2))
        assert result["canonical_guest_count"] == 2

    def test_airbnb_guest_count(self):
        result = normalize_schema("airbnb", _airbnb_payload(guest_count=3))
        assert result["canonical_guest_count"] == 3

    def test_expedia_guest_count_nested(self):
        result = normalize_schema("expedia", _expedia_payload(guests={"count": 4}))
        assert result["canonical_guest_count"] == 4

    def test_agoda_guest_count(self):
        result = normalize_schema("agoda", _agoda_payload(num_guests=1))
        assert result["canonical_guest_count"] == 1

    def test_tripcom_guest_count(self):
        result = normalize_schema("tripcom", _tripcom_payload(guests=5))
        assert result["canonical_guest_count"] == 5


# ---------------------------------------------------------------------------
# Group B — canonical_booking_ref
# ---------------------------------------------------------------------------

class TestCanonicalBookingRef:

    def test_bookingcom_booking_ref(self):
        result = normalize_schema("bookingcom", _bookingcom_payload())
        assert result["canonical_booking_ref"] == "RES-001"

    def test_airbnb_booking_ref(self):
        result = normalize_schema("airbnb", _airbnb_payload())
        assert result["canonical_booking_ref"] == "AB-001"

    def test_expedia_booking_ref(self):
        result = normalize_schema("expedia", _expedia_payload())
        assert result["canonical_booking_ref"] == "EX-001"

    def test_agoda_booking_ref(self):
        result = normalize_schema("agoda", _agoda_payload())
        assert result["canonical_booking_ref"] == "AGD-001"

    def test_tripcom_booking_ref(self):
        result = normalize_schema("tripcom", _tripcom_payload())
        assert result["canonical_booking_ref"] == "TC-001"


# ---------------------------------------------------------------------------
# Group C — canonical_property_id
# ---------------------------------------------------------------------------

class TestCanonicalPropertyId:

    def test_bookingcom_property_id(self):
        result = normalize_schema("bookingcom", _bookingcom_payload())
        assert result["canonical_property_id"] == "PROP-BC-1"

    def test_airbnb_property_id(self):
        result = normalize_schema("airbnb", _airbnb_payload())
        assert result["canonical_property_id"] == "LISTING-1"

    def test_expedia_property_id(self):
        result = normalize_schema("expedia", _expedia_payload())
        assert result["canonical_property_id"] == "PROP-EX-1"

    def test_agoda_property_id(self):
        result = normalize_schema("agoda", _agoda_payload())
        assert result["canonical_property_id"] == "PROP-AG-1"

    def test_tripcom_property_id(self):
        result = normalize_schema("tripcom", _tripcom_payload())
        assert result["canonical_property_id"] == "HOTEL-1"


# ---------------------------------------------------------------------------
# Group D — raw original fields are preserved after normalization
# ---------------------------------------------------------------------------

class TestRawFieldsPreserved:

    def test_bookingcom_raw_fields_preserved(self):
        payload = _bookingcom_payload()
        result = normalize_schema("bookingcom", payload)
        assert result["reservation_id"] == "RES-001"
        assert result["property_id"] == "PROP-BC-1"
        assert result["number_of_guests"] == 2

    def test_airbnb_raw_fields_preserved(self):
        payload = _airbnb_payload()
        result = normalize_schema("airbnb", payload)
        assert result["reservation_id"] == "AB-001"
        assert result["listing_id"] == "LISTING-1"
        assert result["guest_count"] == 3

    def test_expedia_raw_fields_preserved(self):
        payload = _expedia_payload()
        result = normalize_schema("expedia", payload)
        assert result["reservation_id"] == "EX-001"
        assert result["guests"] == {"count": 4}

    def test_agoda_raw_fields_preserved(self):
        payload = _agoda_payload()
        result = normalize_schema("agoda", payload)
        assert result["booking_ref"] == "AGD-001"
        assert result["num_guests"] == 1

    def test_tripcom_raw_fields_preserved(self):
        payload = _tripcom_payload()
        result = normalize_schema("tripcom", payload)
        assert result["order_id"] == "TC-001"
        assert result["hotel_id"] == "HOTEL-1"

    def test_normalize_schema_returns_copy_not_original(self):
        """normalize_schema must not mutate the original payload dict."""
        payload = _bookingcom_payload()
        original_keys = set(payload.keys())
        normalize_schema("bookingcom", payload)
        assert set(payload.keys()) == original_keys


# ---------------------------------------------------------------------------
# Group E — missing fields yield None, never raise
# ---------------------------------------------------------------------------

class TestMissingFieldsYieldNone:

    def test_bookingcom_missing_guest_count(self):
        payload = _bookingcom_payload()
        del payload["number_of_guests"]
        result = normalize_schema("bookingcom", payload)
        assert result["canonical_guest_count"] is None

    def test_airbnb_missing_listing_id(self):
        payload = _airbnb_payload()
        del payload["listing_id"]
        result = normalize_schema("airbnb", payload)
        assert result["canonical_property_id"] is None

    def test_expedia_missing_nested_guests(self):
        payload = _expedia_payload()
        del payload["guests"]
        result = normalize_schema("expedia", payload)
        assert result["canonical_guest_count"] is None

    def test_agoda_missing_booking_ref(self):
        payload = _agoda_payload()
        del payload["booking_ref"]
        result = normalize_schema("agoda", payload)
        assert result["canonical_booking_ref"] is None

    def test_tripcom_missing_hotel_id(self):
        payload = _tripcom_payload()
        del payload["hotel_id"]
        result = normalize_schema("tripcom", payload)
        assert result["canonical_property_id"] is None

    def test_unknown_provider_all_none(self):
        """Unknown provider should not raise — all canonical fields are None."""
        result = normalize_schema("unknown_provider", {"some_field": "value"})
        assert result["canonical_guest_count"] is None
        assert result["canonical_booking_ref"] is None
        assert result["canonical_property_id"] is None
        assert result["some_field"] == "value"
