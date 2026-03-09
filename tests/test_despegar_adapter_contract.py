"""
Phase 98 — Despegar Adapter Contract Tests

Tests the DespegarAdapter end-to-end:
  - normalize(): reservation_code (DSP- prefix), hotel_id, passenger_count, check_in/check_out
  - to_canonical_envelope(): BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED
  - Financial extraction via _extract_despegar (total_fare/despegar_fee/net_amount)
  - booking_identity: DSP- prefix stripping
  - Amendment extraction via extract_amendment_despegar
  - Pipeline integration via process_ota_event
  - Idempotency: determinism + uniqueness

Test groups:
  A — Adapter registration and instantiation
  B — normalize() field mapping
  C — to_canonical_envelope() for all three event types
  D — Financial extractor
  E — booking_identity: DSP- prefix stripping
  F — Amendment extractor
  G — Pipeline integration (process_ota_event)
  H — Idempotency: determinism + uniqueness
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from adapters.ota.despegar import DespegarAdapter
from adapters.ota.registry import get_adapter
from adapters.ota.pipeline import process_ota_event
from adapters.ota.schemas import CanonicalEnvelope
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.financial_extractor import extract_financial_facts, CONFIDENCE_FULL, CONFIDENCE_ESTIMATED, CONFIDENCE_PARTIAL
from adapters.ota.amendment_extractor import extract_amendment_despegar
from datetime import datetime


# ---------------------------------------------------------------------------
# Test payload factories
# ---------------------------------------------------------------------------

TENANT = "tenant-despegar-test-01"


def _despegar_create_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "dsp-evt-create-001",
        "event_type": "BOOKING_CONFIRMED",
        "reservation_code": "DSP-AR-9988001",
        "hotel_id": "DSP-HOTEL-BA-001",
        "check_in": "2026-11-15",
        "check_out": "2026-11-20",
        "passenger_count": 2,
        "total_fare": "75000.00",
        "despegar_fee": "11250.00",
        "net_amount": "63750.00",
        "currency": "ARS",
        "occurred_at": "2026-07-01T08:00:00",
    }
    base.update(overrides)
    return base


def _despegar_cancel_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "dsp-evt-cancel-001",
        "event_type": "BOOKING_CANCELLED",
        "reservation_code": "DSP-AR-9988001",
        "hotel_id": "DSP-HOTEL-BA-001",
        "check_in": "2026-11-15",
        "check_out": "2026-11-20",
        "passenger_count": 2,
        "total_fare": "75000.00",
        "currency": "ARS",
        "occurred_at": "2026-07-02T08:00:00",
    }
    base.update(overrides)
    return base


def _despegar_amend_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "dsp-evt-amend-001",
        "event_type": "BOOKING_MODIFIED",
        "reservation_code": "DSP-AR-9988001",
        "hotel_id": "DSP-HOTEL-BA-001",
        "check_in": "2026-11-15",
        "check_out": "2026-11-20",
        "passenger_count": 2,
        "total_fare": "82000.00",
        "currency": "ARS",
        "occurred_at": "2026-07-03T08:00:00",
        "modification": {
            "check_in": "2026-11-18",
            "check_out": "2026-11-23",
            "passenger_count": 3,
            "reason": "extended stay",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — Adapter registration and instantiation
# ---------------------------------------------------------------------------

class TestGroupARegistration:

    def test_a1_adapter_registered(self) -> None:
        adapter = get_adapter("despegar")
        assert adapter is not None

    def test_a2_adapter_is_despegar(self) -> None:
        adapter = get_adapter("despegar")
        assert isinstance(adapter, DespegarAdapter)

    def test_a3_provider_slug(self) -> None:
        assert DespegarAdapter.provider == "despegar"

    def test_a4_adapter_has_normalize(self) -> None:
        assert hasattr(DespegarAdapter(), "normalize")

    def test_a5_adapter_has_to_canonical_envelope(self) -> None:
        assert hasattr(DespegarAdapter(), "to_canonical_envelope")


# ---------------------------------------------------------------------------
# Group B — normalize() field mapping
# ---------------------------------------------------------------------------

class TestGroupBNormalize:

    def _norm(self, payload: dict):
        return DespegarAdapter().normalize(payload)

    def test_b1_tenant_id_preserved(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.tenant_id == TENANT

    def test_b2_provider_is_despegar(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.provider == "despegar"

    def test_b3_external_event_id(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.external_event_id == "dsp-evt-create-001"

    def test_b4_reservation_code_dsp_prefix_stripped(self) -> None:
        n = self._norm(_despegar_create_payload())
        # DSP-AR-9988001 → strip "DSP-" → AR-9988001 → lowercase → ar-9988001
        assert n.reservation_id == "ar-9988001"

    def test_b5_hotel_id_as_property_id(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.property_id == "DSP-HOTEL-BA-001"

    def test_b6_occurred_at_parsed(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert isinstance(n.occurred_at, datetime)

    def test_b7_financial_facts_attached(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.financial_facts is not None
        assert n.financial_facts.provider == "despegar"

    def test_b8_canonical_check_in(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_check_in"] == "2026-11-15"

    def test_b9_canonical_check_out(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_check_out"] == "2026-11-20"

    def test_b10_canonical_guest_count_from_passenger_count(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_guest_count"] == 2

    def test_b11_canonical_total_price_from_total_fare(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_total_price"] == "75000.00"

    def test_b12_canonical_currency_ars(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_currency"] == "ARS"

    def test_b13_canonical_booking_ref(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_booking_ref"] == "DSP-AR-9988001"

    def test_b14_canonical_property_id(self) -> None:
        n = self._norm(_despegar_create_payload())
        assert n.payload["canonical_property_id"] == "DSP-HOTEL-BA-001"


# ---------------------------------------------------------------------------
# Group C — to_canonical_envelope() all event types
# ---------------------------------------------------------------------------

class TestGroupCCanonicalEnvelope:

    def test_c1_booking_created_type(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.type == "BOOKING_CREATED"

    def test_c2_booking_canceled_type(self) -> None:
        env = process_ota_event("despegar", _despegar_cancel_payload(), TENANT)
        assert env.type == "BOOKING_CANCELED"

    def test_c3_booking_amended_type(self) -> None:
        env = process_ota_event("despegar", _despegar_amend_payload(), TENANT)
        assert env.type == "BOOKING_AMENDED"

    def test_c4_envelope_is_canonical(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert isinstance(env, CanonicalEnvelope)

    def test_c5_tenant_id_in_envelope(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.tenant_id == TENANT

    def test_c6_provider_in_payload(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.payload["provider"] == "despegar"

    def test_c7_reservation_id_in_payload(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.payload["reservation_id"] == "ar-9988001"

    def test_c8_property_id_in_payload(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.payload["property_id"] == "DSP-HOTEL-BA-001"

    def test_c9_idempotency_key_contains_despegar(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert "despegar" in env.idempotency_key

    def test_c10_amended_payload_has_amendment_fields(self) -> None:
        env = process_ota_event("despegar", _despegar_amend_payload(), TENANT)
        assert "new_check_in" in env.payload
        assert "new_check_out" in env.payload
        assert "new_guest_count" in env.payload

    def test_c11_amended_new_check_in(self) -> None:
        env = process_ota_event("despegar", _despegar_amend_payload(), TENANT)
        assert env.payload["new_check_in"] == "2026-11-18"

    def test_c12_amended_new_passenger_count(self) -> None:
        env = process_ota_event("despegar", _despegar_amend_payload(), TENANT)
        assert env.payload["new_guest_count"] == 3

    def test_c13_booking_id_in_amended_payload(self) -> None:
        env = process_ota_event("despegar", _despegar_amend_payload(), TENANT)
        assert env.payload["booking_id"] == "despegar_ar-9988001"

    def test_c14_occurred_at_not_none(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.occurred_at is not None


# ---------------------------------------------------------------------------
# Group D — Financial extractor
# ---------------------------------------------------------------------------

class TestGroupDFinancial:

    def test_d1_full_confidence_when_all_present(self) -> None:
        facts = extract_financial_facts("despegar", _despegar_create_payload())
        assert facts.source_confidence == CONFIDENCE_FULL

    def test_d2_total_price_from_total_fare(self) -> None:
        facts = extract_financial_facts("despegar", _despegar_create_payload())
        assert facts.total_price == Decimal("75000.00")

    def test_d3_commission_from_despegar_fee(self) -> None:
        facts = extract_financial_facts("despegar", _despegar_create_payload())
        assert facts.ota_commission == Decimal("11250.00")

    def test_d4_net_payout_extracted(self) -> None:
        facts = extract_financial_facts("despegar", _despegar_create_payload())
        assert facts.net_to_property == Decimal("63750.00")

    def test_d5_currency_ars(self) -> None:
        facts = extract_financial_facts("despegar", _despegar_create_payload())
        assert facts.currency == "ARS"

    def test_d6_estimated_when_net_derived(self) -> None:
        payload = _despegar_create_payload()
        del payload["net_amount"]
        facts = extract_financial_facts("despegar", payload)
        assert facts.source_confidence == CONFIDENCE_ESTIMATED
        assert facts.net_to_property == Decimal("63750.00")

    def test_d7_partial_when_currency_missing(self) -> None:
        payload = _despegar_create_payload()
        del payload["currency"]
        del payload["net_amount"]
        del payload["despegar_fee"]
        facts = extract_financial_facts("despegar", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL

    def test_d8_provider_is_despegar(self) -> None:
        facts = extract_financial_facts("despegar", _despegar_create_payload())
        assert facts.provider == "despegar"

    def test_d9_brl_currency_supported(self) -> None:
        payload = _despegar_create_payload(currency="BRL", total_fare="2800.00",
                                           despegar_fee="420.00", net_amount="2380.00")
        facts = extract_financial_facts("despegar", payload)
        assert facts.currency == "BRL"
        assert facts.total_price == Decimal("2800.00")


# ---------------------------------------------------------------------------
# Group E — booking_identity: DSP- prefix stripping
# ---------------------------------------------------------------------------

class TestGroupEBookingIdentity:

    def test_e1_dsp_prefix_stripped_upper(self) -> None:
        result = normalize_reservation_ref("despegar", "DSP-AR-9988001")
        assert result == "ar-9988001"

    def test_e2_dsp_prefix_stripped_lower(self) -> None:
        result = normalize_reservation_ref("despegar", "dsp-ar-9988001")
        assert result == "ar-9988001"

    def test_e3_no_prefix_passthrough(self) -> None:
        result = normalize_reservation_ref("despegar", "AR-9988001")
        assert result == "ar-9988001"

    def test_e4_empty_ref(self) -> None:
        result = normalize_reservation_ref("despegar", "")
        assert result == ""

    def test_e5_whitespace_stripped(self) -> None:
        result = normalize_reservation_ref("despegar", "  DSP-MX-7777  ")
        assert result == "mx-7777"


# ---------------------------------------------------------------------------
# Group F — Amendment extractor
# ---------------------------------------------------------------------------

class TestGroupFAmendment:

    def test_f1_check_in_extracted(self) -> None:
        amend = extract_amendment_despegar(_despegar_amend_payload())
        assert amend.new_check_in == "2026-11-18"

    def test_f2_check_out_extracted(self) -> None:
        amend = extract_amendment_despegar(_despegar_amend_payload())
        assert amend.new_check_out == "2026-11-23"

    def test_f3_passenger_count_extracted(self) -> None:
        amend = extract_amendment_despegar(_despegar_amend_payload())
        assert amend.new_guest_count == 3

    def test_f4_reason_extracted(self) -> None:
        amend = extract_amendment_despegar(_despegar_amend_payload())
        assert amend.amendment_reason == "extended stay"

    def test_f5_missing_modification_block_returns_nones(self) -> None:
        payload = _despegar_create_payload()  # no modification block
        amend = extract_amendment_despegar(payload)
        assert amend.new_check_in is None
        assert amend.new_check_out is None
        assert amend.new_guest_count is None
        assert amend.amendment_reason is None


# ---------------------------------------------------------------------------
# Group G — Pipeline integration
# ---------------------------------------------------------------------------

class TestGroupGPipeline:

    def test_g1_process_ota_event_create(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.type == "BOOKING_CREATED"

    def test_g2_process_ota_event_cancel(self) -> None:
        env = process_ota_event("despegar", _despegar_cancel_payload(), TENANT)
        assert env.type == "BOOKING_CANCELED"

    def test_g3_process_ota_event_amend(self) -> None:
        env = process_ota_event("despegar", _despegar_amend_payload(), TENANT)
        assert env.type == "BOOKING_AMENDED"

    def test_g4_envelope_has_idempotency_key(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.idempotency_key
        assert isinstance(env.idempotency_key, str)

    def test_g5_idempotency_key_format(self) -> None:
        env = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env.idempotency_key.startswith("despegar:")


# ---------------------------------------------------------------------------
# Group H — Idempotency: determinism + uniqueness
# ---------------------------------------------------------------------------

class TestGroupHIdempotency:

    def test_h1_same_payload_same_key(self) -> None:
        env1 = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        env2 = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        assert env1.idempotency_key == env2.idempotency_key

    def test_h2_different_event_id_different_key(self) -> None:
        env1 = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        env2 = process_ota_event(
            "despegar",
            _despegar_create_payload(event_id="dsp-evt-create-999"),
            TENANT,
        )
        assert env1.idempotency_key != env2.idempotency_key

    def test_h3_create_and_cancel_different_keys(self) -> None:
        create = process_ota_event("despegar", _despegar_create_payload(), TENANT)
        cancel = process_ota_event("despegar", _despegar_cancel_payload(), TENANT)
        assert create.idempotency_key != cancel.idempotency_key

    def test_h4_same_cancel_twice_same_key(self) -> None:
        env1 = process_ota_event("despegar", _despegar_cancel_payload(), TENANT)
        env2 = process_ota_event("despegar", _despegar_cancel_payload(), TENANT)
        assert env1.idempotency_key == env2.idempotency_key
