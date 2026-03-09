"""
Phase 85 — Contract tests for GVRAdapter (Google Vacation Rentals).

Tests:
  A — GVRAdapter.normalize() — basic field extraction
  B — GVRAdapter.to_canonical_envelope() — BOOKING_CREATED
  C — GVRAdapter.to_canonical_envelope() — BOOKING_CANCELED
  D — GVRAdapter.to_canonical_envelope() — BOOKING_AMENDED
  E — Financial extraction for GVR (including net derivation)
  F — Schema normalization includes gvr
  G — Registry: get_adapter("gvr") resolves correctly
  H — Booking identity: normalize_reservation_ref("gvr", ...) applies base rules
  I — Architecture: connected_ota preserved in non-amended envelope
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from adapters.ota.gvr import GVRAdapter
from adapters.ota.financial_extractor import extract_financial_facts
from adapters.ota.schema_normalizer import normalize_schema
from adapters.ota.registry import get_adapter
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.schemas import ClassifiedBookingEvent


# ---------------------------------------------------------------------------
# Shared payload fixture helpers
# ---------------------------------------------------------------------------

def _base_payload(**overrides) -> dict:
    base = {
        "event_id": "gvr-evt-001",
        "gvr_booking_id": "GVR-ABCDEF12",
        "property_id": "prop-xyz-789",
        "occurred_at": "2026-11-01T10:00:00",
        "event_type": "RESERVATION_CREATED",
        "tenant_id": "tenant-gvr",
        "guest_count": 3,
        "check_in": "2026-12-10",
        "check_out": "2026-12-17",
        "currency": "USD",
        "booking_value": "700.00",
        "google_fee": "70.00",
        "net_amount": "630.00",
        "connected_ota": "bookingcom",
    }
    base.update(overrides)
    return base


def _make_adapter() -> GVRAdapter:
    return GVRAdapter()


def _normalize(payload: dict = None):
    if payload is None:
        payload = _base_payload()
    return _make_adapter().normalize(payload)


def _classify(normalized, semantic_kind: str):
    return ClassifiedBookingEvent(
        normalized=normalized,
        semantic_kind=semantic_kind,
    )


# ---------------------------------------------------------------------------
# Group A — normalize()
# ---------------------------------------------------------------------------

class TestGVRAdapterNormalize:

    def test_A1_provider_is_gvr(self) -> None:
        assert _make_adapter().provider == "gvr"

    def test_A2_tenant_id_extracted(self) -> None:
        assert _normalize().tenant_id == "tenant-gvr"

    def test_A3_external_event_id_from_event_id(self) -> None:
        assert _normalize().external_event_id == "gvr-evt-001"

    def test_A4_property_id_from_property_id(self) -> None:
        assert _normalize().property_id == "prop-xyz-789"

    def test_A5_reservation_id_from_gvr_booking_id(self) -> None:
        # normalize_reservation_ref: strip + lowercase
        result = _normalize()
        assert result.reservation_id == "gvr-abcdef12"

    def test_A6_occurred_at_is_datetime(self) -> None:
        assert isinstance(_normalize().occurred_at, datetime)

    def test_A7_financial_facts_attached(self) -> None:
        result = _normalize()
        assert result.financial_facts is not None
        assert result.financial_facts.provider == "gvr"

    def test_A8_connected_ota_preserved_in_payload(self) -> None:
        result = _normalize()
        assert result.payload.get("connected_ota") == "bookingcom"


# ---------------------------------------------------------------------------
# Group B — to_canonical_envelope (BOOKING_CREATED)
# ---------------------------------------------------------------------------

class TestGVREnvelopeCreated:

    def _envelope(self):
        return _make_adapter().to_canonical_envelope(
            _classify(_normalize(), "CREATE")
        )

    def test_B1_type_is_booking_created(self) -> None:
        assert self._envelope().type == "BOOKING_CREATED"

    def test_B2_tenant_id_preserved(self) -> None:
        assert self._envelope().tenant_id == "tenant-gvr"

    def test_B3_payload_has_provider_gvr(self) -> None:
        assert self._envelope().payload["provider"] == "gvr"

    def test_B4_reservation_id_normalized(self) -> None:
        assert self._envelope().payload["reservation_id"] == "gvr-abcdef12"

    def test_B5_property_id_preserved(self) -> None:
        assert self._envelope().payload["property_id"] == "prop-xyz-789"

    def test_B6_connected_ota_in_payload(self) -> None:
        assert self._envelope().payload["connected_ota"] == "bookingcom"

    def test_B7_idempotency_key_deterministic(self) -> None:
        env1 = self._envelope()
        env2 = self._envelope()
        assert env1.idempotency_key == env2.idempotency_key

    def test_B8_no_connected_ota_payload_none(self) -> None:
        payload = _base_payload()
        del payload["connected_ota"]
        normalized = _normalize(payload)
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "CREATE"))
        assert env.payload.get("connected_ota") is None


# ---------------------------------------------------------------------------
# Group C — to_canonical_envelope (BOOKING_CANCELED)
# ---------------------------------------------------------------------------

class TestGVREnvelopeCanceled:

    def test_C1_type_is_booking_canceled(self) -> None:
        normalized = _normalize()
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "CANCEL"))
        assert env.type == "BOOKING_CANCELED"

    def test_C2_idempotency_key_differs_from_created(self) -> None:
        normalized = _normalize()
        create_env = _make_adapter().to_canonical_envelope(_classify(normalized, "CREATE"))
        cancel_env = _make_adapter().to_canonical_envelope(_classify(normalized, "CANCEL"))
        assert create_env.idempotency_key != cancel_env.idempotency_key


# ---------------------------------------------------------------------------
# Group D — to_canonical_envelope (BOOKING_AMENDED)
# ---------------------------------------------------------------------------

class TestGVREnvelopeAmended:

    def _amended_payload(self):
        return _base_payload(**{
            "modification": {
                "check_in": "2026-12-15",
                "check_out": "2026-12-22",
                "guest_count": 4,
                "reason": "date_change",
            }
        })

    def test_D1_type_is_booking_amended(self) -> None:
        normalized = _normalize(self._amended_payload())
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "BOOKING_AMENDED"))
        assert env.type == "BOOKING_AMENDED"

    def test_D2_booking_id_in_payload(self) -> None:
        normalized = _normalize(self._amended_payload())
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "BOOKING_AMENDED"))
        assert env.payload["booking_id"] == "gvr_gvr-abcdef12"

    def test_D3_amendment_fields_extracted(self) -> None:
        normalized = _normalize(self._amended_payload())
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "BOOKING_AMENDED"))
        assert env.payload["new_check_in"] == "2026-12-15"
        assert env.payload["new_check_out"] == "2026-12-22"
        assert env.payload["new_guest_count"] == 4
        assert env.payload["amendment_reason"] == "date_change"

    def test_D4_unsupported_kind_raises(self) -> None:
        normalized = _normalize()
        with pytest.raises(ValueError):
            _make_adapter().to_canonical_envelope(_classify(normalized, "UNKNOWN_SEMANTIC"))


# ---------------------------------------------------------------------------
# Group E — Financial extraction
# ---------------------------------------------------------------------------

class TestGVRFinancialExtraction:

    def test_E1_provider_is_gvr(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.provider == "gvr"

    def test_E2_total_price_from_booking_value(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.total_price == Decimal("700.00")

    def test_E3_net_to_property_from_net_amount(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.net_to_property == Decimal("630.00")

    def test_E4_google_fee_is_ota_commission(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.ota_commission == Decimal("70.00")

    def test_E5_google_fee_is_fees(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.fees == Decimal("70.00")

    def test_E6_currency_extracted(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.currency == "USD"

    def test_E7_net_derived_when_absent(self) -> None:
        """When net_amount is not present, derive net = booking_value - google_fee."""
        payload = _base_payload()
        del payload["net_amount"]
        facts = extract_financial_facts("gvr", payload)
        assert facts.net_to_property == Decimal("630.00")
        assert facts.source_confidence == "ESTIMATED"

    def test_E8_confidence_full_when_all_present(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.source_confidence == "FULL"

    def test_E9_confidence_partial_when_currency_missing(self) -> None:
        payload = _base_payload()
        del payload["currency"]
        facts = extract_financial_facts("gvr", payload)
        assert facts.source_confidence == "PARTIAL"

    def test_E10_raw_financial_fields_captured(self) -> None:
        facts = extract_financial_facts("gvr", _base_payload())
        assert "booking_value" in facts.raw_financial_fields
        assert "google_fee" in facts.raw_financial_fields

    def test_E11_no_google_fee_gives_none_commission(self) -> None:
        payload = _base_payload()
        del payload["google_fee"]
        facts = extract_financial_facts("gvr", payload)
        assert facts.ota_commission is None

    def test_E12_taxes_always_none(self) -> None:
        """GVR does not expose taxes separately."""
        facts = extract_financial_facts("gvr", _base_payload())
        assert facts.taxes is None


# ---------------------------------------------------------------------------
# Group F — Schema normalization
# ---------------------------------------------------------------------------

class TestGVRSchemaNormalization:

    def test_F1_canonical_guest_count(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_guest_count"] == 3

    def test_F2_canonical_booking_ref_from_gvr_booking_id(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_booking_ref"] == "GVR-ABCDEF12"

    def test_F3_canonical_property_id(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_property_id"] == "prop-xyz-789"

    def test_F4_canonical_check_in_from_check_in(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_check_in"] == "2026-12-10"

    def test_F5_canonical_check_out_from_check_out(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_check_out"] == "2026-12-17"

    def test_F6_canonical_currency(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_currency"] == "USD"

    def test_F7_canonical_total_price_from_booking_value(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["canonical_total_price"] == "700.00"

    def test_F8_original_keys_preserved(self) -> None:
        enriched = normalize_schema("gvr", _base_payload())
        assert enriched["gvr_booking_id"] == "GVR-ABCDEF12"
        assert enriched["property_id"] == "prop-xyz-789"


# ---------------------------------------------------------------------------
# Group G — Registry
# ---------------------------------------------------------------------------

class TestGVRRegistry:

    def test_G1_get_adapter_gvr_resolves(self) -> None:
        assert get_adapter("gvr") is not None

    def test_G2_resolved_adapter_is_gvr(self) -> None:
        assert get_adapter("gvr").provider == "gvr"

    def test_G3_resolved_adapter_is_gvr_type(self) -> None:
        assert isinstance(get_adapter("gvr"), GVRAdapter)


# ---------------------------------------------------------------------------
# Group H — Booking identity
# ---------------------------------------------------------------------------

class TestGVRBookingIdentity:

    def test_H1_base_normalization_strips_whitespace(self) -> None:
        ref = normalize_reservation_ref("gvr", "  GVR-ABCDEF12  ")
        assert ref == "gvr-abcdef12"

    def test_H2_lowercase_applied(self) -> None:
        ref = normalize_reservation_ref("gvr", "GVR-UPPER")
        assert ref == ref.lower()


# ---------------------------------------------------------------------------
# Group I — GVR Architecture difference assertions
# ---------------------------------------------------------------------------

class TestGVRArchitecture:

    def test_I1_connected_ota_present_in_created_envelope(self) -> None:
        """GVR-specific: connected_ota field forwarded for routing visibility."""
        normalized = _normalize(_base_payload(connected_ota="expedia"))
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "CREATE"))
        assert env.payload["connected_ota"] == "expedia"

    def test_I2_booking_id_format_gvr_prefix(self) -> None:
        """Phase 36 invariant: booking_id = '{provider}_{reservation_id}'."""
        normalized = _normalize()
        booking_id = f"gvr_{normalized.reservation_id}"
        assert booking_id == "gvr_gvr-abcdef12"

    def test_I3_canonical_booking_id_in_amended_envelope(self) -> None:
        """Amendment booking_id follows Phase 36 invariant."""
        amended = _base_payload(**{"modification": {
            "check_in": "2026-12-15",
            "check_out": "2026-12-22",
            "guest_count": 2,
            "reason": "guest_request",
        }})
        normalized = _normalize(amended)
        env = _make_adapter().to_canonical_envelope(_classify(normalized, "BOOKING_AMENDED"))
        assert env.payload["booking_id"] == "gvr_gvr-abcdef12"
