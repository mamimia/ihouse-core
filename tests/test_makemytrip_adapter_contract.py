"""
Phase 94 — MakeMyTrip Adapter Contract Tests

Tests the MakemytripAdapter end-to-end:
  - normalize(): field extraction, prefix stripping, schema normalization
  - to_canonical_envelope(): BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED
  - Financial extraction via _extract_makemytrip
  - Semantics classification: booking_confirmed/cancelled/modified
  - booking_identity: MMT- prefix stripping
  - Idempotency key format
  - Amendment extraction via extract_amendment_makemytrip
  - Pipeline integration via process_ota_event

Test groups:
  A — Adapter registration and instantiation
  B — normalize() field mapping
  C — to_canonical_envelope() for all three event types
  D — Financial extractor
  E — Semantics: booking_confirmed / booking_cancelled / booking_modified
  F — booking_identity: MMT- prefix stripping
  G — Amendment extractor
  H — Pipeline integration (process_ota_event)
  I — Idempotency: determinism + uniqueness
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from adapters.ota.makemytrip import MakemytripAdapter
from adapters.ota.registry import get_adapter
from adapters.ota.pipeline import process_ota_event
from adapters.ota.schemas import CanonicalEnvelope
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.financial_extractor import extract_financial_facts, CONFIDENCE_FULL, CONFIDENCE_ESTIMATED, CONFIDENCE_PARTIAL
from adapters.ota.amendment_extractor import extract_amendment_makemytrip
from adapters.ota.semantics import classify_normalized_event
from adapters.ota.schemas import NormalizedBookingEvent
from datetime import datetime


# ---------------------------------------------------------------------------
# Test payload factories
# ---------------------------------------------------------------------------

TENANT = "tenant-mmt-test-01"


def _mmt_create_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "mmt-evt-create-001",
        "event_type": "booking_confirmed",
        "booking_id": "MMT-IN-9876543210",
        "hotel_id": "MMT-HOTEL-001",
        "check_in": "2026-09-10",
        "check_out": "2026-09-15",
        "guest_count": 2,
        "order_value": "12500.00",
        "mmt_commission": "1250.00",
        "net_amount": "11250.00",
        "currency": "INR",
        "occurred_at": "2026-06-01T10:00:00",
        "reservation_id": "MMT-IN-9876543210",  # payload_validator
    }
    base.update(overrides)
    return base


def _mmt_cancel_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "mmt-evt-cancel-001",
        "event_type": "booking_cancelled",
        "booking_id": "MMT-IN-9876543210",
        "hotel_id": "MMT-HOTEL-001",
        "check_in": "2026-09-10",
        "check_out": "2026-09-15",
        "guest_count": 2,
        "order_value": "12500.00",
        "mmt_commission": "1250.00",
        "net_amount": "11250.00",
        "currency": "INR",
        "occurred_at": "2026-06-02T10:00:00",
        "reservation_id": "MMT-IN-9876543210",
    }
    base.update(overrides)
    return base


def _mmt_amend_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "mmt-evt-amend-001",
        "event_type": "booking_modified",
        "booking_id": "MMT-IN-9876543210",
        "hotel_id": "MMT-HOTEL-001",
        "check_in": "2026-09-10",
        "check_out": "2026-09-15",
        "guest_count": 2,
        "order_value": "13000.00",
        "currency": "INR",
        "occurred_at": "2026-06-03T10:00:00",
        "reservation_id": "MMT-IN-9876543210",
        "amendment": {
            "check_in": "2026-09-12",
            "check_out": "2026-09-17",
            "guests": 3,
            "reason": "guest request",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — Adapter registration and instantiation
# ---------------------------------------------------------------------------

class TestGroupARegistration:

    def test_a1_adapter_registered(self) -> None:
        adapter = get_adapter("makemytrip")
        assert adapter is not None

    def test_a2_adapter_is_makemytrip(self) -> None:
        adapter = get_adapter("makemytrip")
        assert isinstance(adapter, MakemytripAdapter)

    def test_a3_provider_slug(self) -> None:
        assert MakemytripAdapter.provider == "makemytrip"

    def test_a4_adapter_has_normalize(self) -> None:
        assert hasattr(MakemytripAdapter(), "normalize")

    def test_a5_adapter_has_to_canonical_envelope(self) -> None:
        assert hasattr(MakemytripAdapter(), "to_canonical_envelope")


# ---------------------------------------------------------------------------
# Group B — normalize() field mapping
# ---------------------------------------------------------------------------

class TestGroupBNormalize:

    def _norm(self, payload: dict):
        return MakemytripAdapter().normalize(payload)

    def test_b1_tenant_id_preserved(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.tenant_id == TENANT

    def test_b2_provider_is_makemytrip(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.provider == "makemytrip"

    def test_b3_external_event_id(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.external_event_id == "mmt-evt-create-001"

    def test_b4_reservation_id_mmt_prefix_stripped(self) -> None:
        n = self._norm(_mmt_create_payload())
        # MMT-IN-9876543210 → in-9876543210 (strip "mmt-" 4 chars)
        assert n.reservation_id == "in-9876543210"

    def test_b5_property_id_from_hotel_id(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.property_id == "MMT-HOTEL-001"

    def test_b6_occurred_at_parsed(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert isinstance(n.occurred_at, datetime)

    def test_b7_financial_facts_attached(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.financial_facts is not None
        assert n.financial_facts.provider == "makemytrip"

    def test_b8_canonical_check_in(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_check_in"] == "2026-09-10"

    def test_b9_canonical_check_out(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_check_out"] == "2026-09-15"

    def test_b10_canonical_guest_count(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_guest_count"] == 2

    def test_b11_canonical_total_price(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_total_price"] == "12500.00"

    def test_b12_canonical_currency_inr(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_currency"] == "INR"

    def test_b13_canonical_booking_ref(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_booking_ref"] == "MMT-IN-9876543210"

    def test_b14_canonical_property_id(self) -> None:
        n = self._norm(_mmt_create_payload())
        assert n.payload["canonical_property_id"] == "MMT-HOTEL-001"


# ---------------------------------------------------------------------------
# Group C — to_canonical_envelope() all event types
# ---------------------------------------------------------------------------

class TestGroupCCanonicalEnvelope:

    def test_c1_booking_created_type(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.type == "BOOKING_CREATED"

    def test_c2_booking_canceled_type(self) -> None:
        env = process_ota_event("makemytrip", _mmt_cancel_payload(), TENANT)
        assert env.type == "BOOKING_CANCELED"

    def test_c3_booking_amended_type(self) -> None:
        env = process_ota_event("makemytrip", _mmt_amend_payload(), TENANT)
        assert env.type == "BOOKING_AMENDED"

    def test_c4_envelope_is_canonical(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert isinstance(env, CanonicalEnvelope)

    def test_c5_tenant_id_in_envelope(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.tenant_id == TENANT

    def test_c6_provider_in_payload(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.payload["provider"] == "makemytrip"

    def test_c7_reservation_id_in_payload(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.payload["reservation_id"] == "in-9876543210"

    def test_c8_property_id_in_payload(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.payload["property_id"] == "MMT-HOTEL-001"

    def test_c9_idempotency_key_contains_makemytrip(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert "makemytrip" in env.idempotency_key

    def test_c10_amended_payload_has_amendment_fields(self) -> None:
        env = process_ota_event("makemytrip", _mmt_amend_payload(), TENANT)
        assert "new_check_in" in env.payload
        assert "new_check_out" in env.payload
        assert "new_guest_count" in env.payload

    def test_c11_amended_new_check_in(self) -> None:
        env = process_ota_event("makemytrip", _mmt_amend_payload(), TENANT)
        assert env.payload["new_check_in"] == "2026-09-12"

    def test_c12_amended_new_guest_count(self) -> None:
        env = process_ota_event("makemytrip", _mmt_amend_payload(), TENANT)
        assert env.payload["new_guest_count"] == 3

    def test_c13_booking_id_in_amended_payload(self) -> None:
        env = process_ota_event("makemytrip", _mmt_amend_payload(), TENANT)
        assert env.payload["booking_id"] == "makemytrip_in-9876543210"

    def test_c14_occurred_at_not_none(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.occurred_at is not None


# ---------------------------------------------------------------------------
# Group D — Financial extractor
# ---------------------------------------------------------------------------

class TestGroupDFinancial:

    def test_d1_full_confidence_when_all_present(self) -> None:
        facts = extract_financial_facts("makemytrip", _mmt_create_payload())
        assert facts.source_confidence == CONFIDENCE_FULL

    def test_d2_total_price_extracted(self) -> None:
        facts = extract_financial_facts("makemytrip", _mmt_create_payload())
        assert facts.total_price == Decimal("12500.00")

    def test_d3_commission_extracted(self) -> None:
        facts = extract_financial_facts("makemytrip", _mmt_create_payload())
        assert facts.ota_commission == Decimal("1250.00")

    def test_d4_net_extracted(self) -> None:
        facts = extract_financial_facts("makemytrip", _mmt_create_payload())
        assert facts.net_to_property == Decimal("11250.00")

    def test_d5_currency_inr(self) -> None:
        facts = extract_financial_facts("makemytrip", _mmt_create_payload())
        assert facts.currency == "INR"

    def test_d6_estimated_when_net_derived(self) -> None:
        payload = _mmt_create_payload()
        del payload["net_amount"]
        facts = extract_financial_facts("makemytrip", payload)
        assert facts.source_confidence == CONFIDENCE_ESTIMATED
        assert facts.net_to_property == Decimal("11250.00")

    def test_d7_partial_when_missing_currency_and_commission(self) -> None:
        """PARTIAL only when no commission to derive net AND no net directly."""
        payload = _mmt_create_payload()
        del payload["currency"]
        del payload["net_amount"]
        del payload["mmt_commission"]
        facts = extract_financial_facts("makemytrip", payload)
        # No commission → can't derive net → currency also missing → PARTIAL
        assert facts.source_confidence == CONFIDENCE_PARTIAL

    def test_d8_provider_is_makemytrip(self) -> None:
        facts = extract_financial_facts("makemytrip", _mmt_create_payload())
        assert facts.provider == "makemytrip"


# ---------------------------------------------------------------------------
# Group E — Semantics: MMT event_type aliases
# ---------------------------------------------------------------------------

class TestGroupESemantics:

    def _make_event(self, event_type: str) -> NormalizedBookingEvent:
        return NormalizedBookingEvent(
            tenant_id=TENANT,
            provider="makemytrip",
            external_event_id="evt-001",
            reservation_id="in-9876543210",
            property_id="MMT-HOTEL-001",
            occurred_at=datetime(2026, 6, 1),
            payload={"event_type": event_type},
            financial_facts=None,
        )

    def test_e1_booking_confirmed_maps_to_create(self) -> None:
        classified = classify_normalized_event(self._make_event("booking_confirmed"))
        assert classified.semantic_kind == "CREATE"

    def test_e2_booking_cancelled_maps_to_cancel(self) -> None:
        classified = classify_normalized_event(self._make_event("booking_cancelled"))
        assert classified.semantic_kind == "CANCEL"

    def test_e3_booking_canceled_maps_to_cancel(self) -> None:
        classified = classify_normalized_event(self._make_event("booking_canceled"))
        assert classified.semantic_kind == "CANCEL"

    def test_e4_booking_modified_maps_to_amended(self) -> None:
        classified = classify_normalized_event(self._make_event("booking_modified"))
        assert classified.semantic_kind == "BOOKING_AMENDED"

    def test_e5_unknown_type_raises(self) -> None:
        with pytest.raises(ValueError):
            classify_normalized_event(self._make_event("unknown_event_xyz"))

    def test_e6_traveloka_booking_confirmed_also_works(self) -> None:
        """semantics.py change benefits Traveloka as well."""
        event = NormalizedBookingEvent(
            tenant_id=TENANT,
            provider="traveloka",
            external_event_id="tv-evt-001",
            reservation_id="tv-12345",
            property_id="TV-HOTEL-001",
            occurred_at=datetime(2026, 6, 1),
            payload={"event_type": "booking_confirmed"},
            financial_facts=None,
        )
        classified = classify_normalized_event(event)
        assert classified.semantic_kind == "CREATE"


# ---------------------------------------------------------------------------
# Group F — booking_identity: MMT- prefix stripping
# ---------------------------------------------------------------------------

class TestGroupFBookingIdentity:

    def test_f1_mmt_prefix_stripped_upper(self) -> None:
        result = normalize_reservation_ref("makemytrip", "MMT-IN-9876543210")
        assert result == "in-9876543210"

    def test_f2_mmt_prefix_stripped_lower(self) -> None:
        result = normalize_reservation_ref("makemytrip", "mmt-in-9876543210")
        assert result == "in-9876543210"

    def test_f3_no_prefix_passthrough(self) -> None:
        result = normalize_reservation_ref("makemytrip", "IN-9876543210")
        assert result == "in-9876543210"

    def test_f4_empty_ref_passthrough(self) -> None:
        result = normalize_reservation_ref("makemytrip", "")
        assert result == ""

    def test_f5_whitespace_stripped(self) -> None:
        result = normalize_reservation_ref("makemytrip", "  MMT-IN-001  ")
        assert result == "in-001"


# ---------------------------------------------------------------------------
# Group G — Amendment extractor
# ---------------------------------------------------------------------------

class TestGroupGAmendment:

    def test_g1_check_in_extracted(self) -> None:
        amend = extract_amendment_makemytrip(_mmt_amend_payload())
        assert amend.new_check_in == "2026-09-12"

    def test_g2_check_out_extracted(self) -> None:
        amend = extract_amendment_makemytrip(_mmt_amend_payload())
        assert amend.new_check_out == "2026-09-17"

    def test_g3_guest_count_extracted(self) -> None:
        amend = extract_amendment_makemytrip(_mmt_amend_payload())
        assert amend.new_guest_count == 3

    def test_g4_reason_extracted(self) -> None:
        amend = extract_amendment_makemytrip(_mmt_amend_payload())
        assert amend.amendment_reason == "guest request"

    def test_g5_missing_amendment_block_returns_nones(self) -> None:
        payload = _mmt_create_payload()  # no amendment block
        amend = extract_amendment_makemytrip(payload)
        assert amend.new_check_in is None
        assert amend.new_check_out is None
        assert amend.new_guest_count is None
        assert amend.amendment_reason is None


# ---------------------------------------------------------------------------
# Group H — Pipeline integration
# ---------------------------------------------------------------------------

class TestGroupHPipeline:

    def test_h1_process_ota_event_create(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.type == "BOOKING_CREATED"

    def test_h2_process_ota_event_cancel(self) -> None:
        env = process_ota_event("makemytrip", _mmt_cancel_payload(), TENANT)
        assert env.type == "BOOKING_CANCELED"

    def test_h3_process_ota_event_amend(self) -> None:
        env = process_ota_event("makemytrip", _mmt_amend_payload(), TENANT)
        assert env.type == "BOOKING_AMENDED"

    def test_h4_envelope_has_idempotency_key(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.idempotency_key
        assert isinstance(env.idempotency_key, str)

    def test_h5_idempotency_key_format(self) -> None:
        env = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env.idempotency_key.startswith("makemytrip:")


# ---------------------------------------------------------------------------
# Group I — Idempotency: determinism + uniqueness
# ---------------------------------------------------------------------------

class TestGroupIIdempotency:

    def test_i1_same_payload_same_key(self) -> None:
        env1 = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        env2 = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        assert env1.idempotency_key == env2.idempotency_key

    def test_i2_different_event_id_different_key(self) -> None:
        env1 = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        env2 = process_ota_event(
            "makemytrip",
            _mmt_create_payload(event_id="mmt-evt-create-999"),
            TENANT,
        )
        assert env1.idempotency_key != env2.idempotency_key

    def test_i3_create_and_cancel_different_keys(self) -> None:
        create = process_ota_event("makemytrip", _mmt_create_payload(), TENANT)
        cancel = process_ota_event("makemytrip", _mmt_cancel_payload(), TENANT)
        assert create.idempotency_key != cancel.idempotency_key

    def test_i4_same_cancel_twice_same_key(self) -> None:
        env1 = process_ota_event("makemytrip", _mmt_cancel_payload(), TENANT)
        env2 = process_ota_event("makemytrip", _mmt_cancel_payload(), TENANT)
        assert env1.idempotency_key == env2.idempotency_key
