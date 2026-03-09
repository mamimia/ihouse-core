"""
Phase 83 — Contract tests for VrboAdapter.

Tests:
  A — VrboAdapter.normalize() — basic field extraction
  B — VrboAdapter.to_canonical_envelope() — BOOKING_CREATED
  C — VrboAdapter.to_canonical_envelope() — BOOKING_CANCELED
  D — VrboAdapter.to_canonical_envelope() — BOOKING_AMENDED
  E — Financial extraction for Vrbo
  F — Schema normalization includes vrbo
  G — Registry: get_adapter("vrbo") resolves correctly
  H — Booking identity: normalize_reservation_ref("vrbo", ...) applies base rules
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from adapters.ota.vrbo import VrboAdapter
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
        "event_id": "vrbo-evt-001",
        "reservation_id": "VR123456",
        "unit_id": "unit-789",
        "occurred_at": "2026-10-01T10:00:00",
        "event_type": "RESERVATION_CREATED",
        "tenant_id": "tenant-vrbo",
        "guest_count": 2,
        "arrival_date": "2026-11-15",
        "departure_date": "2026-11-22",
        "currency": "USD",
        "traveler_payment": "500.00",
        "manager_payment": "425.00",
        "service_fee": "75.00",
    }
    base.update(overrides)
    return base


def _make_adapter() -> VrboAdapter:
    return VrboAdapter()


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

class TestVrboAdapterNormalize:

    def test_A1_provider_is_vrbo(self) -> None:
        assert _make_adapter().provider == "vrbo"

    def test_A2_tenant_id_extracted(self) -> None:
        result = _normalize()
        assert result.tenant_id == "tenant-vrbo"

    def test_A3_external_event_id(self) -> None:
        result = _normalize()
        assert result.external_event_id == "vrbo-evt-001"

    def test_A4_property_id_from_unit_id(self) -> None:
        result = _normalize()
        assert result.property_id == "unit-789"

    def test_A5_reservation_id_normalized(self) -> None:
        result = _normalize()
        # normalize_reservation_ref: strip + lowercase
        assert result.reservation_id == "vr123456"

    def test_A6_occurred_at_is_datetime(self) -> None:
        result = _normalize()
        assert isinstance(result.occurred_at, datetime)

    def test_A7_payload_is_dict(self) -> None:
        result = _normalize()
        assert isinstance(result.payload, dict)

    def test_A8_financial_facts_attached(self) -> None:
        result = _normalize()
        assert result.financial_facts is not None
        assert result.financial_facts.provider == "vrbo"


# ---------------------------------------------------------------------------
# Group B — to_canonical_envelope (BOOKING_CREATED)
# ---------------------------------------------------------------------------

class TestVrboEnvelopeCreated:

    def _envelope(self):
        normalized = _normalize()
        classified = _classify(normalized, "CREATE")
        return _make_adapter().to_canonical_envelope(classified)

    def test_B1_type_is_booking_created(self) -> None:
        assert self._envelope().type == "BOOKING_CREATED"

    def test_B2_tenant_id_preserved(self) -> None:
        assert self._envelope().tenant_id == "tenant-vrbo"

    def test_B3_payload_has_provider(self) -> None:
        assert self._envelope().payload["provider"] == "vrbo"

    def test_B4_payload_has_reservation_id(self) -> None:
        # normalized (lowercase)
        assert self._envelope().payload["reservation_id"] == "vr123456"

    def test_B5_payload_has_property_id(self) -> None:
        assert self._envelope().payload["property_id"] == "unit-789"

    def test_B6_idempotency_key_deterministic(self) -> None:
        env1 = self._envelope()
        env2 = self._envelope()
        assert env1.idempotency_key == env2.idempotency_key

    def test_B7_occurred_at_is_datetime(self) -> None:
        assert isinstance(self._envelope().occurred_at, datetime)


# ---------------------------------------------------------------------------
# Group C — to_canonical_envelope (BOOKING_CANCELED)
# ---------------------------------------------------------------------------

class TestVrboEnvelopeCanceled:

    def test_C1_type_is_booking_canceled(self) -> None:
        normalized = _normalize()
        classified = _classify(normalized, "CANCEL")
        env = _make_adapter().to_canonical_envelope(classified)
        assert env.type == "BOOKING_CANCELED"

    def test_C2_idempotency_key_differs_from_created(self) -> None:
        normalized = _normalize()
        create_env = _make_adapter().to_canonical_envelope(_classify(normalized, "CREATE"))
        cancel_env = _make_adapter().to_canonical_envelope(_classify(normalized, "CANCEL"))
        assert create_env.idempotency_key != cancel_env.idempotency_key


# ---------------------------------------------------------------------------
# Group D — to_canonical_envelope (BOOKING_AMENDED)
# ---------------------------------------------------------------------------

class TestVrboEnvelopeAmended:

    def _amended_payload(self):
        return _base_payload(**{
            "alteration": {
                "new_check_in": "2026-12-01",
                "new_check_out": "2026-12-08",
                "new_guest_count": 3,
                "amendment_reason": "guest_request",
            },
        })

    def test_D1_type_is_booking_amended(self) -> None:
        normalized = _normalize(self._amended_payload())
        classified = _classify(normalized, "BOOKING_AMENDED")
        env = _make_adapter().to_canonical_envelope(classified)
        assert env.type == "BOOKING_AMENDED"

    def test_D2_booking_id_in_payload(self) -> None:
        normalized = _normalize(self._amended_payload())
        classified = _classify(normalized, "BOOKING_AMENDED")
        env = _make_adapter().to_canonical_envelope(classified)
        assert env.payload["booking_id"] == "vrbo_vr123456"

    def test_D3_amendment_fields_in_payload(self) -> None:
        normalized = _normalize(self._amended_payload())
        classified = _classify(normalized, "BOOKING_AMENDED")
        env = _make_adapter().to_canonical_envelope(classified)
        for field in ("new_check_in", "new_check_out", "new_guest_count", "amendment_reason"):
            assert field in env.payload, f"Missing: {field}"

    def test_D4_unsupported_kind_raises(self) -> None:
        normalized = _normalize()
        classified = _classify(normalized, "UNKNOWN_SEMANTIC")
        with pytest.raises(ValueError):
            _make_adapter().to_canonical_envelope(classified)


# ---------------------------------------------------------------------------
# Group E — Financial extraction
# ---------------------------------------------------------------------------

class TestVrboFinancialExtraction:

    def test_E1_provider_is_vrbo(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.provider == "vrbo"

    def test_E2_total_price_from_traveler_payment(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.total_price == Decimal("500.00")

    def test_E3_net_to_property_from_manager_payment(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.net_to_property == Decimal("425.00")

    def test_E4_fees_from_service_fee(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.fees == Decimal("75.00")

    def test_E5_ota_commission_equals_service_fee(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.ota_commission == Decimal("75.00")

    def test_E6_currency_extracted(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.currency == "USD"

    def test_E7_confidence_full_when_all_present(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert facts.source_confidence == "FULL"

    def test_E8_confidence_partial_when_missing(self) -> None:
        payload = _base_payload()
        del payload["manager_payment"]
        facts = extract_financial_facts("vrbo", payload)
        assert facts.source_confidence == "PARTIAL"

    def test_E9_missing_fields_become_none(self) -> None:
        facts = extract_financial_facts("vrbo", {})
        assert facts.total_price is None
        assert facts.net_to_property is None

    def test_E10_raw_financial_fields_present(self) -> None:
        facts = extract_financial_facts("vrbo", _base_payload())
        assert "traveler_payment" in facts.raw_financial_fields
        assert "manager_payment" in facts.raw_financial_fields


# ---------------------------------------------------------------------------
# Group F — Schema normalization
# ---------------------------------------------------------------------------

class TestVrboSchemaNormalization:

    def test_F1_canonical_guest_count(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_guest_count"] == 2

    def test_F2_canonical_booking_ref(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_booking_ref"] == "VR123456"

    def test_F3_canonical_property_id_from_unit_id(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_property_id"] == "unit-789"

    def test_F4_canonical_check_in_from_arrival_date(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_check_in"] == "2026-11-15"

    def test_F5_canonical_check_out_from_departure_date(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_check_out"] == "2026-11-22"

    def test_F6_canonical_currency(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_currency"] == "USD"

    def test_F7_canonical_total_price(self) -> None:
        enriched = normalize_schema("vrbo", _base_payload())
        assert enriched["canonical_total_price"] == "500.00"

    def test_F8_original_keys_preserved(self) -> None:
        payload = _base_payload()
        enriched = normalize_schema("vrbo", payload)
        assert enriched["unit_id"] == "unit-789"
        assert enriched["reservation_id"] == "VR123456"


# ---------------------------------------------------------------------------
# Group G — Registry
# ---------------------------------------------------------------------------

class TestVrboRegistry:

    def test_G1_get_adapter_vrbo_resolves(self) -> None:
        adapter = get_adapter("vrbo")
        assert adapter is not None

    def test_G2_resolved_adapter_is_vrbo(self) -> None:
        adapter = get_adapter("vrbo")
        assert adapter.provider == "vrbo"

    def test_G3_resolved_adapter_is_vrbo_type(self) -> None:
        assert isinstance(get_adapter("vrbo"), VrboAdapter)


# ---------------------------------------------------------------------------
# Group H — Booking identity
# ---------------------------------------------------------------------------

class TestVrboBookingIdentity:

    def test_H1_base_normalization_applied(self) -> None:
        ref = normalize_reservation_ref("vrbo", "  VR123456  ")
        assert ref == "vr123456"

    def test_H2_lowercase_applied(self) -> None:
        ref = normalize_reservation_ref("vrbo", "VR-UPPER")
        assert ref == ref.lower()

    def test_H3_booking_id_format(self) -> None:
        """booking_id = '{provider}_{reservation_ref}' — Phase 36 invariant."""
        normalized = _normalize()
        booking_id = f"vrbo_{normalized.reservation_id}"
        assert booking_id == "vrbo_vr123456"
