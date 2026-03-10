"""
Phase 195 — Contract tests: Hostelworld OTA Adapter

Groups A–G following the established adapter test pattern.

  A — normalize(): field mapping
  B — Prefix stripping: HW- → stripped
  C — Event type → semantic kind
  D — Financial extraction
  E — Amendment extraction (BOOKING_MODIFIED)
  F — to_canonical_envelope() shape and idempotency key
  G — Replay fixture round-trip (CREATE + CANCEL)
"""
from __future__ import annotations

import sys
import os
import yaml
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from adapters.ota.hostelworld import HostelworldAdapter
from adapters.ota.booking_identity import normalize_reservation_ref
from adapters.ota.registry import get_adapter


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

ADAPTER = HostelworldAdapter()

BASE_PAYLOAD = {
    "reservation_id": "HW-2025-0081234",
    "property_id": "HW-PROP-TH-007",
    "event_id": "evt-hw-create-0081234",
    "event_type": "BOOKING_CREATED",
    "check_in": "2026-04-10",
    "check_out": "2026-04-14",
    "guest_count": 2,
    "total_price": "180.00",
    "hostelworld_fee": "27.00",
    "net_price": "153.00",
    "currency": "EUR",
    "occurred_at": "2026-03-10T08:00:00",
    "tenant_id": "tenant-bkk-01",
}

CANCEL_PAYLOAD = {**BASE_PAYLOAD, "event_type": "BOOKING_CANCELLED", "reservation_id": "HW-2025-0081235", "event_id": "evt-hw-cancel-0081235"}

AMENDMENT_PAYLOAD = {
    **BASE_PAYLOAD,
    "event_type": "BOOKING_MODIFIED",
    "event_id": "evt-hw-amend-0081234",
    "amendment": {
        "check_in": "2026-04-12",
        "check_out": "2026-04-16",
        "guest_count": 3,
        "reason": "Guest extension request",
    },
}


def _classify(payload: dict):
    """Normalize + classify using adapter."""
    normalized = ADAPTER.normalize(payload)
    from adapters.ota.semantics import classify_normalized_event
    return classify_normalized_event(normalized)


# ---------------------------------------------------------------------------
# Group A — normalize(): field mapping
# ---------------------------------------------------------------------------

class TestGroupA_Normalize:

    def test_a1_provider_is_hostelworld(self):
        assert ADAPTER.provider == "hostelworld"

    def test_a2_tenant_id_mapped(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        assert n.tenant_id == "tenant-bkk-01"

    def test_a3_property_id_direct(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        assert n.property_id == "HW-PROP-TH-007"

    def test_a4_external_event_id_mapped(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        assert n.external_event_id == "evt-hw-create-0081234"

    def test_a5_occurred_at_parsed(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        assert n.occurred_at is not None

    def test_a6_provider_field_on_normalized(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        assert n.provider == "hostelworld"


# ---------------------------------------------------------------------------
# Group B — Prefix stripping: HW-
# ---------------------------------------------------------------------------

class TestGroupB_PrefixStripping:

    def test_b1_hw_prefix_stripped(self):
        result = normalize_reservation_ref("hostelworld", "HW-2025-0081234")
        assert result == "2025-0081234"

    def test_b2_lowercase_hw_stripped(self):
        result = normalize_reservation_ref("hostelworld", "hw-2025-0081234")
        assert result == "2025-0081234"

    def test_b3_no_prefix_passes_through(self):
        result = normalize_reservation_ref("hostelworld", "2025-0081234")
        assert result == "2025-0081234"

    def test_b4_normalize_strips_in_adapter(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        # HW-2025-0081234 → 2025-0081234
        assert n.reservation_id == "2025-0081234"

    def test_b5_booking_id_format(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        classified = _classify(BASE_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        payload = envelope.payload
        assert payload["reservation_id"] == "2025-0081234"


# ---------------------------------------------------------------------------
# Group C — Event type → semantic kind
# ---------------------------------------------------------------------------

class TestGroupC_EventTypeMapping:

    def test_c1_booking_created_maps_to_create(self):
        classified = _classify(BASE_PAYLOAD)
        assert classified.semantic_kind == "CREATE"

    def test_c2_booking_cancelled_maps_to_cancel(self):
        classified = _classify(CANCEL_PAYLOAD)
        assert classified.semantic_kind == "CANCEL"

    def test_c3_booking_modified_maps_to_amendment(self):
        classified = _classify(AMENDMENT_PAYLOAD)
        assert classified.semantic_kind == "BOOKING_AMENDED"


# ---------------------------------------------------------------------------
# Group D — Financial extraction
# ---------------------------------------------------------------------------

class TestGroupD_Financial:

    def test_d1_financial_facts_present(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        assert n.financial_facts is not None

    def test_d2_currency_extracted(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        facts = n.financial_facts
        assert facts.currency == "EUR"

    def test_d3_total_price_extracted(self):
        n = ADAPTER.normalize(BASE_PAYLOAD)
        facts = n.financial_facts
        from decimal import Decimal
        assert facts.total_price == Decimal("180.00")

    def test_d4_no_cross_currency_arithmetic(self):
        """Financial facts should carry raw currency code, not a conversion."""
        n = ADAPTER.normalize(BASE_PAYLOAD)
        facts = n.financial_facts
        raw = facts.raw_financial_fields or {}
        assert "usd_equivalent" not in raw
        assert "converted_total" not in raw


# ---------------------------------------------------------------------------
# Group E — Amendment extraction
# ---------------------------------------------------------------------------

class TestGroupE_Amendment:

    def test_e1_amendment_present_for_modified(self):
        n = ADAPTER.normalize(AMENDMENT_PAYLOAD)
        assert "amendment" in n.payload or "canonical_check_in" in n.payload

    def test_e2_new_check_in_extracted(self):
        classified = _classify(AMENDMENT_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.payload.get("new_check_in") == "2026-04-12"

    def test_e3_new_check_out_extracted(self):
        classified = _classify(AMENDMENT_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.payload.get("new_check_out") == "2026-04-16"

    def test_e4_amendment_reason_preserved(self):
        classified = _classify(AMENDMENT_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.payload.get("amendment_reason") == "Guest extension request"


# ---------------------------------------------------------------------------
# Group F — to_canonical_envelope(): shape and idempotency
# ---------------------------------------------------------------------------

class TestGroupF_Envelope:

    def test_f1_create_envelope_type(self):
        classified = _classify(BASE_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CREATED"

    def test_f2_cancel_envelope_type(self):
        classified = _classify(CANCEL_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CANCELED"

    def test_f3_amendment_envelope_type(self):
        classified = _classify(AMENDMENT_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_AMENDED"

    def test_f4_idempotency_key_present(self):
        classified = _classify(BASE_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.idempotency_key is not None
        assert len(envelope.idempotency_key) > 0

    def test_f5_idempotency_key_includes_provider(self):
        classified = _classify(BASE_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert "hostelworld" in envelope.idempotency_key.lower()

    def test_f6_envelope_tenant_id(self):
        classified = _classify(BASE_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.tenant_id == "tenant-bkk-01"

    def test_f7_envelope_provider_in_payload(self):
        classified = _classify(BASE_PAYLOAD)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.payload["provider"] == "hostelworld"

    def test_f8_unsupported_semantic_raises(self):
        from adapters.ota.schemas import ClassifiedBookingEvent
        n = ADAPTER.normalize(BASE_PAYLOAD)
        bad = ClassifiedBookingEvent(normalized=n, semantic_kind="UNKNOWN_KIND")
        with pytest.raises(ValueError, match="Unsupported semantic kind"):
            ADAPTER.to_canonical_envelope(bad)


# ---------------------------------------------------------------------------
# Group G — Replay fixture round-trip
# ---------------------------------------------------------------------------

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "fixtures", "ota_replay", "hostelworld.yaml"
)


class TestGroupG_ReplayFixture:

    @pytest.fixture(scope="class")
    def fixture_data(self):
        with open(FIXTURE_PATH) as f:
            return yaml.safe_load(f)

    def test_g1_fixture_provider_is_hostelworld(self, fixture_data):
        assert fixture_data["provider"] == "hostelworld"

    def test_g2_fixture_has_two_events(self, fixture_data):
        assert len(fixture_data["events"]) == 2

    def test_g3_create_event_normalizes(self, fixture_data):
        create = fixture_data["events"][0]
        n = ADAPTER.normalize(create)
        assert n.provider == "hostelworld"
        assert n.reservation_id == "2025-0081234"   # HW- stripped

    def test_g4_create_event_envelope_type(self, fixture_data):
        create = fixture_data["events"][0]
        classified = _classify(create)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CREATED"

    def test_g5_cancel_event_normalizes(self, fixture_data):
        cancel = fixture_data["events"][1]
        n = ADAPTER.normalize(cancel)
        assert n.provider == "hostelworld"
        assert n.reservation_id == "2025-0081235"   # HW- stripped

    def test_g6_cancel_event_envelope_type(self, fixture_data):
        cancel = fixture_data["events"][1]
        classified = _classify(cancel)
        envelope = ADAPTER.to_canonical_envelope(classified)
        assert envelope.type == "BOOKING_CANCELED"

    def test_g7_registry_returns_hostelworld_adapter(self):
        adapter = get_adapter("hostelworld")
        assert adapter.provider == "hostelworld"
