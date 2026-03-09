"""
Phase 90 — External Integration Test Harness
Phase 102 — Extended to 11 providers (MakeMyTrip, Klook, Despegar added)

End-to-end deterministic pipeline harness for all 11 OTA providers.
Exercises: raw payload → normalize → classify → to_canonical_envelope.
CI-safe: no Supabase, no HTTP, no live API calls anywhere.

Provider coverage:
  bookingcom, expedia, airbnb, agoda, tripcom, vrbo, gvr, traveloka,
  makemytrip, klook, despegar

Groups:
  A — All 11 providers produce valid BOOKING_CREATED envelopes
  B — All 11 providers produce valid BOOKING_CANCELED envelopes
  C — All 11 providers produce valid BOOKING_AMENDED envelopes
  D — booking_id format: '{provider}_{normalized_ref}' across all 11
  E — idempotency_key is non-empty and deterministic for all 11
  F — Invalid payloads rejected (PayloadValidationResult.valid=False)
  G — Cross-provider isolation: same raw reservation_id → different booking_id
  H — Pipeline idempotency: identical payload → identical envelope
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from adapters.ota.pipeline import process_ota_event
from adapters.ota.registry import get_adapter
from adapters.ota.payload_validator import validate_ota_payload
from adapters.ota.schemas import CanonicalEnvelope, ClassifiedBookingEvent
from adapters.ota.booking_identity import normalize_reservation_ref

TENANT = "tenant-harness-01"

# ---------------------------------------------------------------------------
# Canonical provider payload factories
# Each returns a minimal valid payload for that provider.
# ---------------------------------------------------------------------------

def _bookingcom_create() -> dict:
    return {
        "event_id": "bc-evt-10000001",
        "reservation_id": "BK-10000001",
        "property_id": "PROP-BC-1",
        "event_type": "reservation_created",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T08:00:00",
        "check_in": "2026-09-01",
        "check_out": "2026-09-07",
        "num_guests": 2,
        "total_price": "750.00",
        "currency": "EUR",
        "commission": "75.00",
    }


def _bookingcom_cancel() -> dict:
    p = _bookingcom_create()
    p["event_type"] = "reservation_cancelled"
    return p


def _bookingcom_amend() -> dict:
    p = _bookingcom_create()
    p["event_type"] = "reservation_modified"
    p["changes"] = {
        "dates": {"check_in": "2026-09-05", "check_out": "2026-09-10"},
        "guests": 3,
        "reason": "Guest request",
    }
    return p


def _expedia_create() -> dict:
    return {
        "event_id": "ex-evt-20000001",
        "reservation_id": "EXP-20000001",
        "property_id": "PROP-EX-1",
        "event_type": "reservation_created",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T09:00:00",
        "check_in": "2026-10-01",
        "check_out": "2026-10-05",
        "guest_count": 2,
        "total_amount": "480.00",
        "currency": "USD",
        "commission_percent": "15",
    }


def _expedia_cancel() -> dict:
    p = _expedia_create()
    p["event_type"] = "reservation_cancelled"
    return p


def _expedia_amend() -> dict:
    p = _expedia_create()
    p["event_type"] = "reservation_modified"
    p["changes"] = {
        "dates": {"check_in": "2026-10-03", "check_out": "2026-10-08"},
        "guests": {"count": 4},
        "reason": "Extension",
    }
    return p


def _airbnb_create() -> dict:
    return {
        "event_id": "ab-evt-30000001",
        "reservation_id": "ABNB-30000001",
        "listing_id": "LISTING-AB-1",
        "event_type": "reservation_create",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T10:00:00",
        "check_in": "2026-11-01",
        "check_out": "2026-11-06",
        "guest_count": 3,
        "payout_amount": "620.00",
        "booking_subtotal": "700.00",
        "taxes": "80.00",
        "currency": "USD",
    }


def _airbnb_cancel() -> dict:
    p = _airbnb_create()
    p["event_type"] = "reservation_cancel"
    return p


def _airbnb_amend() -> dict:
    p = _airbnb_create()
    p["event_type"] = "alteration_create"
    p["alteration"] = {
        "new_check_in": "2026-11-03",
        "new_check_out": "2026-11-09",
        "new_guest_count": 4,
        "amendment_reason": "Birthday extension",
    }
    return p


def _agoda_create() -> dict:
    return {
        "event_id": "ag-evt-40000001",
        "booking_ref": "AG-40000001",
        "property_id": "PROP-AG-1",
        "event_type": "booking.created",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T11:00:00",
        "check_in": "2026-12-01",
        "check_out": "2026-12-04",
        "num_guests": 2,
        "selling_rate": "330.00",
        "net_rate": "280.50",
        "currency": "THB",
    }


def _agoda_cancel() -> dict:
    p = _agoda_create()
    p["event_type"] = "booking.cancelled"
    return p


def _agoda_amend() -> dict:
    p = _agoda_create()
    p["event_type"] = "booking.modified"
    p["modification"] = {
        "check_in_date": "2026-12-03",
        "check_out_date": "2026-12-07",
        "num_guests": 3,
        "reason": "Date shift",
    }
    return p


def _tripcom_create() -> dict:
    return {
        "event_id": "tc-evt-50000001",
        "order_id": "TC-50000001",
        "hotel_id": "HOTEL-TC-1",
        "event_type": "order_created",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T12:00:00",
        "arrival_date": "2026-11-15",
        "departure_date": "2026-11-20",
        "guest_count": 2,
        "order_amount": "550.00",
        "channel_fee": "55.00",
        "currency": "CNY",
    }


def _tripcom_cancel() -> dict:
    p = _tripcom_create()
    p["event_type"] = "order_cancelled"
    return p


def _tripcom_amend() -> dict:
    p = _tripcom_create()
    p["event_type"] = "order_modified"
    p["changes"] = {
        "check_in": "2026-11-17",
        "check_out": "2026-11-22",
        "guests": 3,
        "remark": "Room change",
    }
    return p


def _vrbo_create() -> dict:
    return {
        "event_id": "vrbo-evt-60000001",
        "reservation_id": "VR60000001",
        "unit_id": "UNIT-VR-1",
        "event_type": "reservation_created",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T13:00:00",
        "arrival_date": "2026-08-10",
        "departure_date": "2026-08-17",
        "guest_count": 4,
        "traveler_payment": "900.00",
        "manager_payment": "765.00",
        "service_fee": "135.00",
        "currency": "USD",
    }


def _vrbo_cancel() -> dict:
    p = _vrbo_create()
    p["event_type"] = "reservation_cancelled"
    return p


def _vrbo_amend() -> dict:
    p = _vrbo_create()
    p["event_type"] = "reservation_modified"
    p["alteration"] = {
        "new_check_in": "2026-08-12",
        "new_check_out": "2026-08-19",
        "new_guest_count": 5,
        "amendment_reason": "Extra night",
    }
    return p


def _gvr_create() -> dict:
    return {
        "event_id": "gvr-evt-70000001",
        "gvr_booking_id": "GVR70000001",
        "reservation_id": "GVR70000001",   # Duplicate for payload_validator boundary check
        "property_id": "PROP-GVR-1",
        "event_type": "reservation_created",
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T14:00:00",
        "check_in": "2026-09-20",
        "check_out": "2026-09-25",
        "guest_count": 2,
        "booking_value": "400.00",
        "google_fee": "40.00",
        "net_amount": "360.00",
        "currency": "EUR",
        "connected_ota": "bookingcom",
    }


def _gvr_cancel() -> dict:
    p = _gvr_create()
    p["event_type"] = "reservation_cancelled"
    return p


def _gvr_amend() -> dict:
    p = _gvr_create()
    p["event_type"] = "reservation_modified"
    p["modification"] = {
        "check_in": "2026-09-22",
        "check_out": "2026-09-27",
        "guest_count": 3,
        "reason": "Late arrival",
    }
    return p


def _traveloka_create() -> dict:
    return {
        "booking_code": "TV-80000001",
        "reservation_id": "TV-80000001",   # Duplicate for payload_validator boundary check
        "event_reference": "tvk-evt-80000001",
        "property_code": "PROP-TV-1",
        "check_in_date": "2026-07-01",
        "check_out_date": "2026-07-05",
        "num_guests": 2,
        "booking_total": "3200.00",
        "traveloka_fee": "320.00",
        "net_payout": "2880.00",
        "currency_code": "THB",
        "event_type": "reservation_created",   # semantics.py: CREATE
        "tenant_id": TENANT,
        "occurred_at": "2026-06-01T15:00:00",
    }


def _traveloka_cancel() -> dict:
    p = _traveloka_create()
    p["event_type"] = "reservation_cancelled"   # maps to CANCEL in semantics.py
    return p


def _traveloka_amend() -> dict:
    p = _traveloka_create()
    p["event_type"] = "modified"    # maps to BOOKING_AMENDED in semantics.py
    p["reservation_id"] = p["booking_code"]   # Keep for validator
    p["modification"] = {
        "check_in_date": "2026-07-03",
        "check_out_date": "2026-07-08",
        "num_guests": 3,
        "modification_reason": "Delayed arrival",
    }
    return p


def _makemytrip_create() -> dict:
    return {
        "event_id":   "mmt-evt-90000001",
        "booking_id": "MMT-IN-9000001",
        "hotel_id":   "HOTEL-MMT-1",
        "event_type": "BOOKING_CONFIRMED",
        "tenant_id":  TENANT,
        "occurred_at": "2026-06-01T16:00:00",
        "check_in":   "2026-10-10",
        "check_out":  "2026-10-14",
        "num_guests": 2,
        "total_amount": "4200.00",
        "mmt_commission": "420.00",
        "net_amount": "3780.00",
        "currency": "INR",
    }


def _makemytrip_cancel() -> dict:
    p = _makemytrip_create()
    p["event_type"] = "BOOKING_CANCELLED"
    return p


def _makemytrip_amend() -> dict:
    p = _makemytrip_create()
    p["event_type"] = "BOOKING_MODIFIED"
    p["amendment"] = {
        "check_in": "2026-10-12",
        "check_out": "2026-10-16",
        "guests": 3,
        "reason": "Date change",
    }
    return p


def _klook_create() -> dict:
    return {
        "event_id":    "klk-evt-10000001",
        "booking_ref": "KL-ACTBK-10000001",
        "activity_id": "ACT-KLK-1",
        "event_type":  "BOOKING_CONFIRMED",
        "tenant_id":   TENANT,
        "occurred_at": "2026-06-01T17:00:00",
        "travel_date":  "2026-11-05",
        "end_date":     "2026-11-06",
        "participants": 4,
        "activity_price": "1200.00",
        "klook_commission": "180.00",
        "net_payout": "1020.00",
        "currency": "HKD",
    }


def _klook_cancel() -> dict:
    p = _klook_create()
    p["event_type"] = "BOOKING_CANCELLED"
    return p


def _klook_amend() -> dict:
    p = _klook_create()
    p["event_type"] = "BOOKING_MODIFIED"
    p["modification"] = {
        "travel_date":  "2026-11-08",
        "end_date":     "2026-11-09",
        "participants": 5,
        "reason":       "Group size change",
    }
    return p


def _despegar_create() -> dict:
    return {
        "event_id":         "dsp-evt-11000001",
        "reservation_code": "DSP-AR-11000001",
        "hotel_id":         "HOTEL-DSP-1",
        "event_type":       "BOOKING_CONFIRMED",
        "tenant_id":        TENANT,
        "occurred_at":      "2026-06-01T18:00:00",
        "check_in":         "2026-12-15",
        "check_out":        "2026-12-20",
        "passenger_count":  2,
        "total_fare":       "85000.00",
        "despegar_fee":     "8500.00",
        "net_amount":       "76500.00",
        "currency":         "ARS",
    }


def _despegar_cancel() -> dict:
    p = _despegar_create()
    p["event_type"] = "BOOKING_CANCELLED"
    return p


def _despegar_amend() -> dict:
    p = _despegar_create()
    p["event_type"] = "BOOKING_MODIFIED"
    p["modification"] = {
        "check_in":         "2026-12-17",
        "check_out":        "2026-12-22",
        "passenger_count":  3,
        "reason":           "Extended stay",
    }
    return p


PROVIDERS = [
    ("bookingcom",  _bookingcom_create,  _bookingcom_cancel,  _bookingcom_amend,  "reservation_id"),
    ("expedia",     _expedia_create,     _expedia_cancel,     _expedia_amend,     "reservation_id"),
    ("airbnb",      _airbnb_create,      _airbnb_cancel,      _airbnb_amend,      "reservation_id"),
    ("agoda",       _agoda_create,       _agoda_cancel,       _agoda_amend,       "booking_ref"),
    ("tripcom",     _tripcom_create,     _tripcom_cancel,     _tripcom_amend,     "order_id"),
    ("vrbo",        _vrbo_create,        _vrbo_cancel,        _vrbo_amend,        "reservation_id"),
    ("gvr",         _gvr_create,         _gvr_cancel,         _gvr_amend,         "gvr_booking_id"),
    ("traveloka",   _traveloka_create,   _traveloka_cancel,   _traveloka_amend,   "booking_code"),
    ("makemytrip",  _makemytrip_create,  _makemytrip_cancel,  _makemytrip_amend,  "booking_id"),
    ("klook",       _klook_create,       _klook_cancel,       _klook_amend,       "booking_ref"),
    ("despegar",    _despegar_create,    _despegar_cancel,    _despegar_amend,    "reservation_code"),
]

PROVIDER_NAMES = [p[0] for p in PROVIDERS]
PROVIDER_CREATE = {p[0]: p[1] for p in PROVIDERS}
PROVIDER_CANCEL = {p[0]: p[2] for p in PROVIDERS}
PROVIDER_AMEND  = {p[0]: p[3] for p in PROVIDERS}
PROVIDER_REF_KEY = {p[0]: p[4] for p in PROVIDERS}


def _run_pipeline(provider: str, payload: dict) -> CanonicalEnvelope:
    """Run the full pipeline (normalize → classify → to_canonical_envelope)."""
    return process_ota_event(provider, payload, TENANT)


# ---------------------------------------------------------------------------
# Group A — All 8 providers: BOOKING_CREATED
# ---------------------------------------------------------------------------

class TestGroupAAllProvidersCreated:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a1_pipeline_produces_booking_created(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.type == "BOOKING_CREATED", (
            f"{provider}: expected BOOKING_CREATED, got {envelope.type}"
        )

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a2_envelope_is_canonical_envelope(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert isinstance(envelope, CanonicalEnvelope)

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a3_envelope_has_tenant_id(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.tenant_id == TENANT

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a4_payload_has_provider_field(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.payload.get("provider") == provider

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a5_payload_has_reservation_id(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert "reservation_id" in envelope.payload
        assert envelope.payload["reservation_id"]

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a6_payload_has_property_id(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert "property_id" in envelope.payload
        assert envelope.payload["property_id"]

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a7_occurred_at_present(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.occurred_at is not None

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_a8_idempotency_key_non_empty(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.idempotency_key
        assert len(str(envelope.idempotency_key)) > 0


# ---------------------------------------------------------------------------
# Group B — All 8 providers: BOOKING_CANCELED
# ---------------------------------------------------------------------------

class TestGroupBAllProvidersCanceled:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_b1_pipeline_produces_booking_canceled(self, provider):
        payload = PROVIDER_CANCEL[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.type == "BOOKING_CANCELED", (
            f"{provider}: expected BOOKING_CANCELED, got {envelope.type}"
        )

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_b2_canceled_envelope_has_provider_field(self, provider):
        payload = PROVIDER_CANCEL[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.payload.get("provider") == provider

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_b3_canceled_idempotency_key_differs_from_created(self, provider):
        create_env = _run_pipeline(provider, PROVIDER_CREATE[provider]())
        cancel_env = _run_pipeline(provider, PROVIDER_CANCEL[provider]())
        # Different event type → different key (even if same reservation_id)
        assert create_env.idempotency_key != cancel_env.idempotency_key

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_b4_canceled_tenant_id_preserved(self, provider):
        payload = PROVIDER_CANCEL[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.tenant_id == TENANT


# ---------------------------------------------------------------------------
# Group C — All 8 providers: BOOKING_AMENDED
# ---------------------------------------------------------------------------

class TestGroupCAllProvidersAmended:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_c1_pipeline_produces_booking_amended(self, provider):
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.type == "BOOKING_AMENDED", (
            f"{provider}: expected BOOKING_AMENDED, got {envelope.type}"
        )

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_c2_amended_envelope_has_booking_id(self, provider):
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        assert "booking_id" in envelope.payload
        assert envelope.payload["booking_id"]

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_c3_amended_envelope_has_new_check_in_key(self, provider):
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        assert "new_check_in" in envelope.payload

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_c4_amended_envelope_has_new_check_out_key(self, provider):
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        assert "new_check_out" in envelope.payload

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_c5_amended_booking_id_starts_with_provider(self, provider):
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        booking_id = envelope.payload["booking_id"]
        assert booking_id.startswith(f"{provider}_"), (
            f"{provider}: booking_id should start with '{provider}_', got {booking_id!r}"
        )

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_c6_amended_tenant_id_preserved(self, provider):
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        assert envelope.tenant_id == TENANT


# ---------------------------------------------------------------------------
# Group D — booking_id format invariant: '{provider}_{normalized_ref}'
# ---------------------------------------------------------------------------

class TestGroupDBookingIdInvariant:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_d1_amended_booking_id_matches_phase36_rule(self, provider):
        """booking_id = '{source}_{reservation_ref}' — Phase 36 invariant."""
        payload = PROVIDER_AMEND[provider]()
        envelope = _run_pipeline(provider, payload)
        booking_id = envelope.payload["booking_id"]
        # Must have exactly one underscore-separated prefix matching provider
        assert booking_id.startswith(f"{provider}_")
        ref_part = booking_id[len(provider) + 1:]
        assert ref_part, f"{provider}: ref_part of booking_id is empty"

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_d2_reservation_id_in_created_envelope_is_normalized(self, provider):
        """reservation_id in CREATE envelope must be lowercase (post-normalization)."""
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        res_id = envelope.payload["reservation_id"]
        assert res_id == res_id.lower(), (
            f"{provider}: reservation_id should be lowercase, got {res_id!r}"
        )

    def test_d3_bookingcom_strips_bk_prefix(self):
        payload = _bookingcom_create()
        payload["reservation_id"] = "BK-10000001"
        envelope = _run_pipeline("bookingcom", payload)
        # After normalization BK- is stripped
        assert "bk-" not in envelope.payload["reservation_id"]

    def test_d4_agoda_strips_ag_prefix(self):
        payload = _agoda_create()
        payload["booking_ref"] = "AG-40000001"
        envelope = _run_pipeline("agoda", payload)
        assert "ag-" not in envelope.payload["reservation_id"]

    def test_d5_tripcom_strips_tc_prefix(self):
        payload = _tripcom_create()
        payload["order_id"] = "TC-50000001"
        envelope = _run_pipeline("tripcom", payload)
        assert "tc-" not in envelope.payload["reservation_id"]

    def test_d6_traveloka_strips_tv_prefix(self):
        payload = _traveloka_create()
        payload["booking_code"] = "TV-80000001"
        envelope = _run_pipeline("traveloka", payload)
        assert "tv-" not in envelope.payload["reservation_id"]


# ---------------------------------------------------------------------------
# Group E — idempotency_key is non-empty and deterministic
# ---------------------------------------------------------------------------

class TestGroupEIdempotencyKey:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_e1_idempotency_key_is_non_empty_string(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert isinstance(envelope.idempotency_key, str)
        assert len(envelope.idempotency_key) > 0

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_e2_idempotency_key_is_deterministic(self, provider):
        payload = PROVIDER_CREATE[provider]()
        env1 = _run_pipeline(provider, payload)
        env2 = _run_pipeline(provider, payload)
        assert env1.idempotency_key == env2.idempotency_key

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_e3_create_cancel_amended_keys_all_differ(self, provider):
        create_key = _run_pipeline(provider, PROVIDER_CREATE[provider]()).idempotency_key
        cancel_key = _run_pipeline(provider, PROVIDER_CANCEL[provider]()).idempotency_key
        amend_key  = _run_pipeline(provider, PROVIDER_AMEND[provider]()).idempotency_key
        assert create_key != cancel_key
        assert create_key != amend_key
        assert cancel_key != amend_key

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_e4_idempotency_key_contains_provider(self, provider):
        payload = PROVIDER_CREATE[provider]()
        envelope = _run_pipeline(provider, payload)
        assert provider in envelope.idempotency_key


# ---------------------------------------------------------------------------
# Group F — Invalid payloads rejected at boundary
# ---------------------------------------------------------------------------

class TestGroupFInvalidPayloadRejected:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_f1_empty_payload_is_invalid(self, provider):
        result = validate_ota_payload(provider, {})
        assert result.valid is False

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_f2_missing_occurred_at_invalid(self, provider):
        payload = PROVIDER_CREATE[provider]()
        del payload["occurred_at"]
        result = validate_ota_payload(provider, payload)
        assert result.valid is False

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_f3_none_payload_is_invalid(self, provider):
        result = validate_ota_payload(provider, None)
        assert result.valid is False

    def test_f4_missing_reservation_id_bookingcom_invalid(self):
        payload = _bookingcom_create()
        del payload["reservation_id"]
        result = validate_ota_payload("bookingcom", payload)
        assert result.valid is False

    def test_f5_missing_reservation_id_tripcom_invalid(self):
        payload = _tripcom_create()
        del payload["order_id"]
        result = validate_ota_payload("tripcom", payload)
        assert result.valid is False

    def test_f6_missing_reservation_id_agoda_invalid(self):
        payload = _agoda_create()
        del payload["booking_ref"]
        result = validate_ota_payload("agoda", payload)
        assert result.valid is False

    def test_f7_invalid_occurred_at_format_rejected(self):
        payload = _bookingcom_create()
        payload["occurred_at"] = "not-a-date"
        result = validate_ota_payload("bookingcom", payload)
        assert result.valid is False

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_f8_valid_payloads_pass_boundary_validation(self, provider):
        """Sanity: all canonical test payloads are valid at boundary."""
        payload = PROVIDER_CREATE[provider]()
        payload.setdefault("tenant_id", TENANT)
        result = validate_ota_payload(provider, payload)
        assert result.valid is True, (
            f"{provider}: expected valid=True, got errors={result.errors}"
        )


# ---------------------------------------------------------------------------
# Group G — Cross-provider isolation
# ---------------------------------------------------------------------------

class TestGroupGCrossProviderIsolation:

    SHARED_REF = "SHARED-REF-99999"

    def _make_payload_with_ref(self, provider: str, ref_key: str) -> dict:
        payload = PROVIDER_CREATE[provider]()
        payload[ref_key] = self.SHARED_REF
        return payload

    @pytest.mark.parametrize("p1,p2", [
        ("bookingcom", "expedia"),
        ("airbnb",     "vrbo"),
        ("agoda",      "tripcom"),
        ("gvr",        "traveloka"),
    ])
    def test_g1_same_raw_ref_different_provider_different_booking_id(self, p1, p2):
        """
        Two providers with the same raw reservation_id must produce
        different booking_ids (prefix ensures isolation).
        """
        p1_ref_key = PROVIDER_REF_KEY[p1]
        p2_ref_key = PROVIDER_REF_KEY[p2]

        payload1 = self._make_payload_with_ref(p1, p1_ref_key)
        payload2 = self._make_payload_with_ref(p2, p2_ref_key)

        amend1 = PROVIDER_AMEND[p1]()
        amend1[p1_ref_key] = self.SHARED_REF
        amend2 = PROVIDER_AMEND[p2]()
        amend2[p2_ref_key] = self.SHARED_REF

        env1 = _run_pipeline(p1, amend1)
        env2 = _run_pipeline(p2, amend2)

        booking_id_1 = env1.payload["booking_id"]
        booking_id_2 = env2.payload["booking_id"]

        assert booking_id_1 != booking_id_2, (
            f"Booking IDs collided across {p1} and {p2}: {booking_id_1!r}"
        )
        assert booking_id_1.startswith(f"{p1}_")
        assert booking_id_2.startswith(f"{p2}_")

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_g2_idempotency_key_isolated_per_provider(self, provider):
        """
        Same raw reservation_id in two different providers produces
        different idempotency keys.
        """
        other_providers = [p for p in PROVIDER_NAMES if p != provider]
        p2 = other_providers[0]

        ref_key_1 = PROVIDER_REF_KEY[provider]
        ref_key_2 = PROVIDER_REF_KEY[p2]

        payload1 = PROVIDER_CREATE[provider]()
        payload1[ref_key_1] = "SHARED-KEY-88888"
        payload2 = PROVIDER_CREATE[p2]()
        payload2[ref_key_2] = "SHARED-KEY-88888"

        env1 = _run_pipeline(provider, payload1)
        env2 = _run_pipeline(p2, payload2)

        assert env1.idempotency_key != env2.idempotency_key, (
            f"Idempotency key collision between {provider} and {p2}"
        )


# ---------------------------------------------------------------------------
# Group H — Pipeline idempotency: same input → same output
# ---------------------------------------------------------------------------

class TestGroupHPipelineIdempotency:

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_h1_create_pipeline_is_idempotent(self, provider):
        payload = PROVIDER_CREATE[provider]()
        env1 = _run_pipeline(provider, payload)
        env2 = _run_pipeline(provider, payload)
        assert env1.type == env2.type
        assert env1.tenant_id == env2.tenant_id
        assert env1.idempotency_key == env2.idempotency_key
        assert env1.payload["provider"] == env2.payload["provider"]
        assert env1.payload["reservation_id"] == env2.payload["reservation_id"]

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_h2_cancel_pipeline_is_idempotent(self, provider):
        payload = PROVIDER_CANCEL[provider]()
        env1 = _run_pipeline(provider, payload)
        env2 = _run_pipeline(provider, payload)
        assert env1.type == env2.type
        assert env1.idempotency_key == env2.idempotency_key

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_h3_amend_pipeline_is_idempotent(self, provider):
        payload = PROVIDER_AMEND[provider]()
        env1 = _run_pipeline(provider, payload)
        env2 = _run_pipeline(provider, payload)
        assert env1.type == env2.type
        assert env1.idempotency_key == env2.idempotency_key
        assert env1.payload["booking_id"] == env2.payload["booking_id"]

    @pytest.mark.parametrize("provider", PROVIDER_NAMES)
    def test_h4_pipeline_does_not_mutate_input_payload(self, provider):
        payload = PROVIDER_CREATE[provider]()
        original_keys = set(payload.keys())
        _run_pipeline(provider, payload)
        # Original payload keys should not be altered
        assert set(payload.keys()) == original_keys
