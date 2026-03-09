"""
Phase 96 — Klook Adapter Contract Tests

Tests the KlookAdapter end-to-end:
  - normalize(): booking_ref (KL- prefix), activity_id, participants, travel_date/end_date
  - to_canonical_envelope(): BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED
  - Financial extraction via _extract_klook
  - booking_identity: KL- prefix stripping
  - Idempotency key format
  - Amendment extraction via extract_amendment_klook
  - Pipeline integration via process_ota_event

Test groups:
  A — Adapter registration and instantiation
  B — normalize() field mapping
  C — to_canonical_envelope() for all three event types
  D — Financial extractor
  E — booking_identity: KL- prefix stripping
  F — Amendment extractor
  G — Pipeline integration (process_ota_event)
  H — Idempotency: determinism + uniqueness
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from adapters.ota.klook import KlookAdapter
from adapters.ota.registry import get_adapter
from adapters.ota.pipeline import process_ota_event
from adapters.ota.schemas import CanonicalEnvelope
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.financial_extractor import extract_financial_facts, CONFIDENCE_FULL, CONFIDENCE_ESTIMATED, CONFIDENCE_PARTIAL
from adapters.ota.amendment_extractor import extract_amendment_klook
from datetime import datetime


# ---------------------------------------------------------------------------
# Test payload factories
# ---------------------------------------------------------------------------

TENANT = "tenant-klook-test-01"


def _klook_create_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "kl-evt-create-001",
        "event_type": "BOOKING_CONFIRMED",
        "booking_ref": "KL-ACTBK-88880001",
        "activity_id": "KL-ACT-TOUR-SG-001",
        "travel_date": "2026-09-10",
        "end_date": "2026-09-10",
        "participants": 4,
        "booking_amount": "3200.00",
        "klook_commission": "480.00",
        "net_payout": "2720.00",
        "currency": "SGD",
        "occurred_at": "2026-06-01T10:00:00",
    }
    base.update(overrides)
    return base


def _klook_cancel_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "kl-evt-cancel-001",
        "event_type": "BOOKING_CANCELLED",
        "booking_ref": "KL-ACTBK-88880001",
        "activity_id": "KL-ACT-TOUR-SG-001",
        "travel_date": "2026-09-10",
        "end_date": "2026-09-10",
        "participants": 4,
        "booking_amount": "3200.00",
        "currency": "SGD",
        "occurred_at": "2026-06-02T10:00:00",
    }
    base.update(overrides)
    return base


def _klook_amend_payload(**overrides) -> dict:
    base = {
        "tenant_id": TENANT,
        "event_id": "kl-evt-amend-001",
        "event_type": "BOOKING_MODIFIED",
        "booking_ref": "KL-ACTBK-88880001",
        "activity_id": "KL-ACT-TOUR-SG-001",
        "travel_date": "2026-09-10",
        "end_date": "2026-09-10",
        "participants": 4,
        "booking_amount": "3400.00",
        "currency": "SGD",
        "occurred_at": "2026-06-03T10:00:00",
        "modification": {
            "travel_date": "2026-09-15",
            "end_date": "2026-09-15",
            "participants": 6,
            "reason": "group size increase",
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Group A — Adapter registration and instantiation
# ---------------------------------------------------------------------------

class TestGroupARegistration:

    def test_a1_adapter_registered(self) -> None:
        adapter = get_adapter("klook")
        assert adapter is not None

    def test_a2_adapter_is_klook(self) -> None:
        adapter = get_adapter("klook")
        assert isinstance(adapter, KlookAdapter)

    def test_a3_provider_slug(self) -> None:
        assert KlookAdapter.provider == "klook"

    def test_a4_adapter_has_normalize(self) -> None:
        assert hasattr(KlookAdapter(), "normalize")

    def test_a5_adapter_has_to_canonical_envelope(self) -> None:
        assert hasattr(KlookAdapter(), "to_canonical_envelope")


# ---------------------------------------------------------------------------
# Group B — normalize() field mapping
# ---------------------------------------------------------------------------

class TestGroupBNormalize:

    def _norm(self, payload: dict):
        return KlookAdapter().normalize(payload)

    def test_b1_tenant_id_preserved(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.tenant_id == TENANT

    def test_b2_provider_is_klook(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.provider == "klook"

    def test_b3_external_event_id(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.external_event_id == "kl-evt-create-001"

    def test_b4_booking_ref_kl_prefix_stripped(self) -> None:
        n = self._norm(_klook_create_payload())
        # KL-ACTBK-88880001 → strip "KL-" → ACTBK-88880001 → lowercase → actbk-88880001
        assert n.reservation_id == "actbk-88880001"

    def test_b5_activity_id_as_property_id(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.property_id == "KL-ACT-TOUR-SG-001"

    def test_b6_occurred_at_parsed(self) -> None:
        n = self._norm(_klook_create_payload())
        assert isinstance(n.occurred_at, datetime)

    def test_b7_financial_facts_attached(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.financial_facts is not None
        assert n.financial_facts.provider == "klook"

    def test_b8_canonical_check_in_from_travel_date(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_check_in"] == "2026-09-10"

    def test_b9_canonical_check_out_from_end_date(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_check_out"] == "2026-09-10"

    def test_b10_canonical_guest_count_from_participants(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_guest_count"] == 4

    def test_b11_canonical_total_price(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_total_price"] == "3200.00"

    def test_b12_canonical_currency_sgd(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_currency"] == "SGD"

    def test_b13_canonical_booking_ref(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_booking_ref"] == "KL-ACTBK-88880001"

    def test_b14_canonical_property_id(self) -> None:
        n = self._norm(_klook_create_payload())
        assert n.payload["canonical_property_id"] == "KL-ACT-TOUR-SG-001"


# ---------------------------------------------------------------------------
# Group C — to_canonical_envelope() all event types
# ---------------------------------------------------------------------------

class TestGroupCCanonicalEnvelope:

    def test_c1_booking_created_type(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.type == "BOOKING_CREATED"

    def test_c2_booking_canceled_type(self) -> None:
        env = process_ota_event("klook", _klook_cancel_payload(), TENANT)
        assert env.type == "BOOKING_CANCELED"

    def test_c3_booking_amended_type(self) -> None:
        env = process_ota_event("klook", _klook_amend_payload(), TENANT)
        assert env.type == "BOOKING_AMENDED"

    def test_c4_envelope_is_canonical(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert isinstance(env, CanonicalEnvelope)

    def test_c5_tenant_id_in_envelope(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.tenant_id == TENANT

    def test_c6_provider_in_payload(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.payload["provider"] == "klook"

    def test_c7_reservation_id_in_payload(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.payload["reservation_id"] == "actbk-88880001"

    def test_c8_property_id_in_payload(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.payload["property_id"] == "KL-ACT-TOUR-SG-001"

    def test_c9_idempotency_key_contains_klook(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert "klook" in env.idempotency_key

    def test_c10_amended_payload_has_amendment_fields(self) -> None:
        env = process_ota_event("klook", _klook_amend_payload(), TENANT)
        assert "new_check_in" in env.payload
        assert "new_check_out" in env.payload
        assert "new_guest_count" in env.payload

    def test_c11_amended_new_travel_date(self) -> None:
        env = process_ota_event("klook", _klook_amend_payload(), TENANT)
        assert env.payload["new_check_in"] == "2026-09-15"

    def test_c12_amended_new_participants(self) -> None:
        env = process_ota_event("klook", _klook_amend_payload(), TENANT)
        assert env.payload["new_guest_count"] == 6

    def test_c13_booking_id_in_amended_payload(self) -> None:
        env = process_ota_event("klook", _klook_amend_payload(), TENANT)
        assert env.payload["booking_id"] == "klook_actbk-88880001"

    def test_c14_occurred_at_not_none(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.occurred_at is not None


# ---------------------------------------------------------------------------
# Group D — Financial extractor
# ---------------------------------------------------------------------------

class TestGroupDFinancial:

    def test_d1_full_confidence_when_all_present(self) -> None:
        facts = extract_financial_facts("klook", _klook_create_payload())
        assert facts.source_confidence == CONFIDENCE_FULL

    def test_d2_total_price_extracted(self) -> None:
        facts = extract_financial_facts("klook", _klook_create_payload())
        assert facts.total_price == Decimal("3200.00")

    def test_d3_commission_extracted(self) -> None:
        facts = extract_financial_facts("klook", _klook_create_payload())
        assert facts.ota_commission == Decimal("480.00")

    def test_d4_net_payout_extracted(self) -> None:
        facts = extract_financial_facts("klook", _klook_create_payload())
        assert facts.net_to_property == Decimal("2720.00")

    def test_d5_currency_sgd(self) -> None:
        facts = extract_financial_facts("klook", _klook_create_payload())
        assert facts.currency == "SGD"

    def test_d6_estimated_when_net_derived(self) -> None:
        payload = _klook_create_payload()
        del payload["net_payout"]
        facts = extract_financial_facts("klook", payload)
        assert facts.source_confidence == CONFIDENCE_ESTIMATED
        assert facts.net_to_property == Decimal("2720.00")

    def test_d7_partial_when_no_commission_no_net_no_currency(self) -> None:
        payload = _klook_create_payload()
        del payload["currency"]
        del payload["net_payout"]
        del payload["klook_commission"]
        facts = extract_financial_facts("klook", payload)
        assert facts.source_confidence == CONFIDENCE_PARTIAL

    def test_d8_provider_is_klook(self) -> None:
        facts = extract_financial_facts("klook", _klook_create_payload())
        assert facts.provider == "klook"


# ---------------------------------------------------------------------------
# Group E — booking_identity: KL- prefix stripping
# ---------------------------------------------------------------------------

class TestGroupEBookingIdentity:

    def test_e1_kl_prefix_stripped_upper(self) -> None:
        result = normalize_reservation_ref("klook", "KL-ACTBK-88880001")
        assert result == "actbk-88880001"

    def test_e2_kl_prefix_stripped_lower(self) -> None:
        result = normalize_reservation_ref("klook", "kl-actbk-88880001")
        assert result == "actbk-88880001"

    def test_e3_no_prefix_passthrough(self) -> None:
        result = normalize_reservation_ref("klook", "ACTBK-88880001")
        assert result == "actbk-88880001"

    def test_e4_empty_ref(self) -> None:
        result = normalize_reservation_ref("klook", "")
        assert result == ""

    def test_e5_whitespace_stripped(self) -> None:
        result = normalize_reservation_ref("klook", "  KL-ACTBK-001  ")
        assert result == "actbk-001"


# ---------------------------------------------------------------------------
# Group F — Amendment extractor
# ---------------------------------------------------------------------------

class TestGroupFAmendment:

    def test_f1_travel_date_extracted(self) -> None:
        amend = extract_amendment_klook(_klook_amend_payload())
        assert amend.new_check_in == "2026-09-15"

    def test_f2_end_date_extracted(self) -> None:
        amend = extract_amendment_klook(_klook_amend_payload())
        assert amend.new_check_out == "2026-09-15"

    def test_f3_participants_extracted(self) -> None:
        amend = extract_amendment_klook(_klook_amend_payload())
        assert amend.new_guest_count == 6

    def test_f4_reason_extracted(self) -> None:
        amend = extract_amendment_klook(_klook_amend_payload())
        assert amend.amendment_reason == "group size increase"

    def test_f5_missing_modification_block_returns_nones(self) -> None:
        payload = _klook_create_payload()  # no modification block
        amend = extract_amendment_klook(payload)
        assert amend.new_check_in is None
        assert amend.new_check_out is None
        assert amend.new_guest_count is None
        assert amend.amendment_reason is None


# ---------------------------------------------------------------------------
# Group G — Pipeline integration
# ---------------------------------------------------------------------------

class TestGroupGPipeline:

    def test_g1_process_ota_event_create(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.type == "BOOKING_CREATED"

    def test_g2_process_ota_event_cancel(self) -> None:
        env = process_ota_event("klook", _klook_cancel_payload(), TENANT)
        assert env.type == "BOOKING_CANCELED"

    def test_g3_process_ota_event_amend(self) -> None:
        env = process_ota_event("klook", _klook_amend_payload(), TENANT)
        assert env.type == "BOOKING_AMENDED"

    def test_g4_envelope_has_idempotency_key(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.idempotency_key
        assert isinstance(env.idempotency_key, str)

    def test_g5_idempotency_key_format(self) -> None:
        env = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env.idempotency_key.startswith("klook:")


# ---------------------------------------------------------------------------
# Group H — Idempotency: determinism + uniqueness
# ---------------------------------------------------------------------------

class TestGroupHIdempotency:

    def test_h1_same_payload_same_key(self) -> None:
        env1 = process_ota_event("klook", _klook_create_payload(), TENANT)
        env2 = process_ota_event("klook", _klook_create_payload(), TENANT)
        assert env1.idempotency_key == env2.idempotency_key

    def test_h2_different_event_id_different_key(self) -> None:
        env1 = process_ota_event("klook", _klook_create_payload(), TENANT)
        env2 = process_ota_event(
            "klook",
            _klook_create_payload(event_id="kl-evt-create-999"),
            TENANT,
        )
        assert env1.idempotency_key != env2.idempotency_key

    def test_h3_create_and_cancel_different_keys(self) -> None:
        create = process_ota_event("klook", _klook_create_payload(), TENANT)
        cancel = process_ota_event("klook", _klook_cancel_payload(), TENANT)
        assert create.idempotency_key != cancel.idempotency_key

    def test_h4_same_cancel_twice_same_key(self) -> None:
        env1 = process_ota_event("klook", _klook_cancel_payload(), TENANT)
        env2 = process_ota_event("klook", _klook_cancel_payload(), TENANT)
        assert env1.idempotency_key == env2.idempotency_key
