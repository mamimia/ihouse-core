"""
Phase 187 — Contract Tests: Rakuten Travel Adapter

Covers the full adapter pipeline for the Rakuten Travel OTA.

Groups:
    A — normalize() + to_canonical_envelope() happy path (BOOKING_CREATED)
    B — BOOKING_CANCELLED → BOOKING_CANCELED canonical type
    C — BOOKING_MODIFIED → BOOKING_AMENDED with amendment extraction
    D — prefix stripping: RAK- stripped correctly from booking_ref
    E — financial extractor: total_amount, rakuten_commission, net derivation
    F — registry: adapter registered under "rakuten" key
    G — unsupported semantic kind raises ValueError
"""
from __future__ import annotations

import pytest
from decimal import Decimal
from datetime import datetime

from adapters.ota.rakuten import RakutenAdapter
from adapters.ota.registry import get_adapter
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.financial_extractor import extract_financial_facts


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_PAYLOAD = {
    "booking_ref": "RAK-JP-20250815-001",
    "hotel_code": "prop-tokyo-001",
    "event_id": "evt-rak-001",
    "event_type": "BOOKING_CREATED",
    "check_in": "2025-08-15",
    "check_out": "2025-08-18",
    "guest_count": 2,
    "total_amount": "45000",
    "rakuten_commission": "4500",
    "net_amount": "40500",
    "currency": "JPY",
    "occurred_at": "2025-07-01T10:00:00",
    "tenant_id": "tenant-jp-001",
}

CANCEL_PAYLOAD = {**BASE_PAYLOAD, "event_type": "BOOKING_CANCELLED", "event_id": "evt-rak-002"}
CANCEL_PAYLOAD_LOWER = {**BASE_PAYLOAD, "event_type": "BOOKING_CANCELLED", "event_id": "evt-rak-003"}

AMEND_PAYLOAD = {
    **BASE_PAYLOAD,
    "event_type": "BOOKING_MODIFIED",
    "event_id": "evt-rak-004",
    "modification": {
        "check_in": "2025-08-17",
        "check_out": "2025-08-21",
        "guest_count": 3,
        "reason": "date_change",
    },
}


@pytest.fixture
def adapter() -> RakutenAdapter:
    return RakutenAdapter()


# ---------------------------------------------------------------------------
# Group A — BOOKING_CREATED happy path
# ---------------------------------------------------------------------------

class TestGroupACreate:

    def test_a1_provider_slug(self, adapter):
        assert adapter.provider == "rakuten"

    def test_a2_normalize_tenant_id(self, adapter):
        n = adapter.normalize(BASE_PAYLOAD)
        assert n.tenant_id == "tenant-jp-001"

    def test_a3_normalize_reservation_id_stripped(self, adapter):
        n = adapter.normalize(BASE_PAYLOAD)
        # RAK-JP-20250815-001 → jp-20250815-001
        assert n.reservation_id == "jp-20250815-001"

    def test_a4_normalize_property_id(self, adapter):
        n = adapter.normalize(BASE_PAYLOAD)
        assert n.property_id == "prop-tokyo-001"

    def test_a5_normalize_external_event_id(self, adapter):
        n = adapter.normalize(BASE_PAYLOAD)
        assert n.external_event_id == "evt-rak-001"

    def test_a6_canonical_type_booking_created(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(BASE_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CREATED"

    def test_a7_canonical_payload_fields(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(BASE_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        p = envelope.payload
        assert p["provider"] == "rakuten"
        assert p["reservation_id"] == "jp-20250815-001"
        assert p["property_id"] == "prop-tokyo-001"

    def test_a8_idempotency_key_is_deterministic(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n1 = adapter.normalize(BASE_PAYLOAD)
        n2 = adapter.normalize(BASE_PAYLOAD)
        e1 = adapter.to_canonical_envelope(classify_normalized_event(n1))
        e2 = adapter.to_canonical_envelope(classify_normalized_event(n2))
        assert e1.idempotency_key == e2.idempotency_key

    def test_a9_occurred_at_parsed(self, adapter):
        n = adapter.normalize(BASE_PAYLOAD)
        assert isinstance(n.occurred_at, datetime)


# ---------------------------------------------------------------------------
# Group B — BOOKING_CANCELLED
# ---------------------------------------------------------------------------

class TestGroupBCancel:

    def test_b1_booking_cancelled_maps_to_canceled(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(CANCEL_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CANCELED"

    def test_b2_cancel_canonical_payload_no_amendment_fields(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(CANCEL_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        p = envelope.payload
        assert "new_check_in" not in p
        assert "new_check_out" not in p

    def test_b3_cancel_tenant_preserved(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(CANCEL_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.tenant_id == "tenant-jp-001"


# ---------------------------------------------------------------------------
# Group C — BOOKING_MODIFIED → BOOKING_AMENDED
# ---------------------------------------------------------------------------

class TestGroupCAmend:

    def test_c1_booking_modified_maps_to_amended(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(AMEND_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_AMENDED"

    def test_c2_amendment_new_check_in(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(AMEND_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.payload["new_check_in"] == "2025-08-17"

    def test_c3_amendment_new_check_out(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(AMEND_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.payload["new_check_out"] == "2025-08-21"

    def test_c4_amendment_new_guest_count(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(AMEND_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.payload["new_guest_count"] == 3

    def test_c5_amendment_reason(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(AMEND_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.payload["amendment_reason"] == "date_change"

    def test_c6_amendment_booking_id_correct(self, adapter):
        from adapters.ota.semantics import classify_normalized_event
        n = adapter.normalize(AMEND_PAYLOAD)
        classified = classify_normalized_event(n)
        envelope = adapter.to_canonical_envelope(classified)
        assert envelope.payload["booking_id"] == "rakuten_jp-20250815-001"


# ---------------------------------------------------------------------------
# Group D — prefix stripping
# ---------------------------------------------------------------------------

class TestGroupDPrefixStripping:

    def test_d1_rak_prefix_stripped(self):
        result = normalize_reservation_ref("rakuten", "RAK-JP-20250815-001")
        assert result == "jp-20250815-001"

    def test_d2_lowercase_rak_stripped(self):
        result = normalize_reservation_ref("rakuten", "rak-sg-99001234")
        assert result == "sg-99001234"

    def test_d3_no_prefix_passes_through(self):
        result = normalize_reservation_ref("rakuten", "jp-plain-99001")
        assert result == "jp-plain-99001"

    def test_d4_booking_id_format(self):
        from adapters.ota.booking_identity import build_booking_id
        result = build_booking_id("rakuten", "RAK-JP-20250815-001")
        assert result == "rakuten_jp-20250815-001"

    def test_d5_idempotent_case_normalization(self):
        r1 = normalize_reservation_ref("rakuten", "RAK-JP-001")
        r2 = normalize_reservation_ref("rakuten", "rak-jp-001")
        assert r1 == r2


# ---------------------------------------------------------------------------
# Group E — financial extractor
# ---------------------------------------------------------------------------

class TestGroupEFinancial:

    def test_e1_total_amount_extracted(self):
        facts = extract_financial_facts("rakuten", BASE_PAYLOAD)
        assert facts.total_price == Decimal("45000")

    def test_e2_currency_jpy(self):
        facts = extract_financial_facts("rakuten", BASE_PAYLOAD)
        assert facts.currency == "JPY"

    def test_e3_rakuten_commission_extracted(self):
        facts = extract_financial_facts("rakuten", BASE_PAYLOAD)
        assert facts.ota_commission == Decimal("4500")

    def test_e4_net_to_property_full_when_net_amount_present(self):
        facts = extract_financial_facts("rakuten", BASE_PAYLOAD)
        assert facts.net_to_property == Decimal("40500")
        assert facts.source_confidence == "FULL"

    def test_e5_net_derived_when_absent(self):
        payload = {**BASE_PAYLOAD}
        del payload["net_amount"]
        facts = extract_financial_facts("rakuten", payload)
        assert facts.net_to_property == Decimal("40500")  # 45000 - 4500
        assert facts.source_confidence == "ESTIMATED"

    def test_e6_partial_when_total_missing(self):
        payload = {**BASE_PAYLOAD}
        del payload["total_amount"]
        del payload["net_amount"]
        facts = extract_financial_facts("rakuten", payload)
        assert facts.source_confidence == "PARTIAL"
        assert facts.total_price is None

    def test_e7_raw_financial_fields_preserved(self):
        facts = extract_financial_facts("rakuten", BASE_PAYLOAD)
        assert "total_amount" in facts.raw_financial_fields
        assert "currency" in facts.raw_financial_fields


# ---------------------------------------------------------------------------
# Group F — registry
# ---------------------------------------------------------------------------

class TestGroupFRegistry:

    def test_f1_registered_in_registry(self):
        adapter = get_adapter("rakuten")
        assert adapter is not None

    def test_f2_registry_returns_rakuten_adapter(self):
        adapter = get_adapter("rakuten")
        assert isinstance(adapter, RakutenAdapter)

    def test_f3_provider_slug_matches(self):
        adapter = get_adapter("rakuten")
        assert adapter.provider == "rakuten"


# ---------------------------------------------------------------------------
# Group G — unsupported semantic kind
# ---------------------------------------------------------------------------

class TestGroupGUnsupported:

    def test_g1_unknown_semantic_raises(self, adapter):
        from adapters.ota.schemas import NormalizedBookingEvent, ClassifiedBookingEvent
        n = adapter.normalize(BASE_PAYLOAD)
        classified = ClassifiedBookingEvent(normalized=n, semantic_kind="UNKNOWN_KIND")
        with pytest.raises(ValueError, match="Unsupported semantic kind"):
            adapter.to_canonical_envelope(classified)
