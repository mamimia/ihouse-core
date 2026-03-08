"""
Phase 53 Contract Tests: Expedia Adapter Full Implementation

Verifies that the Expedia OTA adapter correctly handles:
- BOOKING_CREATED (CREATE)
- BOOKING_CANCELED (CANCEL)
- BOOKING_AMENDED (reservation_modified)

All tests are unit/contract — no live Supabase required.

Run:
    cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
    source .venv/bin/activate
    PYTHONPATH=src python3 -m pytest tests/test_expedia_contract.py -v
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from adapters.ota.service import ingest_provider_event
from adapters.ota.expedia import ExpediaAdapter
from adapters.ota.schemas import NormalizedBookingEvent, ClassifiedBookingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _expedia_payload(
    *,
    event_id: str = "exp_evt_001",
    event_type: str = "reservation_created",
    reservation_id: str = "exp_res_001",
    property_id: str = "exp_prop_001",
    tenant_id: str = "tenant_expedia",
    check_in: str | None = "2026-10-01",
    check_out: str | None = "2026-10-07",
    guests: int | None = None,
    reason: str | None = None,
) -> Dict[str, Any]:
    """Build a minimal Expedia webhook payload."""
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "reservation_id": reservation_id,
        "property_id": property_id,
        "occurred_at": "2026-03-08T18:00:00",
        "event_type": event_type,
        "tenant_id": tenant_id,
    }
    # Expedia amendment data lives under 'changes'
    if check_in is not None or check_out is not None or guests is not None or reason is not None:
        changes: Dict[str, Any] = {}
        if check_in is not None or check_out is not None:
            changes["dates"] = {}
            if check_in is not None:
                changes["dates"]["check_in"] = check_in
            if check_out is not None:
                changes["dates"]["check_out"] = check_out
        if guests is not None:
            changes["guests"] = {"count": guests}
        if reason is not None:
            changes["reason"] = reason
        payload["changes"] = changes
    return payload


adapter = ExpediaAdapter()


# ---------------------------------------------------------------------------
# T1: normalize() — field mapping
# ---------------------------------------------------------------------------

class TestExpediaNormalize:
    def test_normalize_maps_all_core_fields(self):
        """normalize() correctly maps Expedia webhook fields to NormalizedBookingEvent."""
        payload = _expedia_payload(event_id="exp_n_001", reservation_id="res_n_001")
        normalized = adapter.normalize(payload)

        assert normalized.provider == "expedia"
        assert normalized.external_event_id == "exp_n_001"
        assert normalized.reservation_id == "res_n_001"
        assert normalized.property_id == "exp_prop_001"
        assert normalized.tenant_id == "tenant_expedia"
        assert isinstance(normalized.occurred_at, datetime)

    def test_normalize_payload_preserved(self):
        """Original payload dict is preserved in normalized.payload."""
        payload = _expedia_payload()
        normalized = adapter.normalize(payload)
        assert normalized.payload == payload


# ---------------------------------------------------------------------------
# T2: BOOKING_CREATED via full pipeline
# ---------------------------------------------------------------------------

class TestExpediaBookingCreated:
    def test_created_envelope_type(self):
        """reservation_created → BOOKING_CREATED canonical envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="reservation_created", event_id="exp_c_001"),
            tenant_id="tenant_expedia",
        )
        assert envelope.type == "BOOKING_CREATED"

    def test_created_idempotency_key_format(self):
        """BOOKING_CREATED key: expedia:booking_created:{event_id}."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="created", event_id="exp_c_002"),
            tenant_id="tenant_expedia",
        )
        assert envelope.idempotency_key == "expedia:booking_created:exp_c_002"

    def test_created_payload_fields(self):
        """BOOKING_CREATED payload has provider, reservation_id, property_id."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="reservation_created", event_id="exp_c_003"),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["provider"] == "expedia"
        assert envelope.payload["reservation_id"] == "exp_res_001"
        assert envelope.payload["property_id"] == "exp_prop_001"

    def test_created_tenant_propagated(self):
        """tenant_id propagates to canonical envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="reservation_created", event_id="exp_c_004"),
            tenant_id="tenant_xyz",
        )
        assert envelope.tenant_id == "tenant_xyz"


# ---------------------------------------------------------------------------
# T3: BOOKING_CANCELED via full pipeline
# ---------------------------------------------------------------------------

class TestExpediaBookingCanceled:
    def test_canceled_envelope_type(self):
        """reservation_cancelled → BOOKING_CANCELED canonical envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="reservation_cancelled", event_id="exp_x_001"),
            tenant_id="tenant_expedia",
        )
        assert envelope.type == "BOOKING_CANCELED"

    def test_canceled_idempotency_key_format(self):
        """BOOKING_CANCELED key: expedia:booking_canceled:{event_id}."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="canceled", event_id="exp_x_002"),
            tenant_id="tenant_expedia",
        )
        assert envelope.idempotency_key == "expedia:booking_canceled:exp_x_002"


# ---------------------------------------------------------------------------
# T4: BOOKING_AMENDED via full pipeline
# ---------------------------------------------------------------------------

class TestExpediaBookingAmended:
    def test_amended_envelope_type(self):
        """reservation_modified → BOOKING_AMENDED canonical envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_001",
                check_in="2026-11-01",
                check_out="2026-11-07",
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.type == "BOOKING_AMENDED"

    def test_amended_booking_id(self):
        """booking_id = expedia_{reservation_id} — same rule as bookingcom."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="modified",
                event_id="exp_a_002",
                reservation_id="res_expedia_999",
                check_in="2026-11-01",
                check_out="2026-11-07",
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["booking_id"] == "expedia_res_expedia_999"

    def test_amended_check_in_propagated(self):
        """new_check_in from changes.dates.check_in propagates to envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_003",
                check_in="2026-12-01",
                check_out=None,
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["new_check_in"] == "2026-12-01"

    def test_amended_check_out_propagated(self):
        """new_check_out from changes.dates.check_out propagates to envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_004",
                check_in=None,
                check_out="2026-12-10",
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["new_check_out"] == "2026-12-10"

    def test_amended_guest_count_propagated(self):
        """new_guest_count from changes.guests.count propagates to envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_005",
                check_in="2026-12-01",
                check_out="2026-12-10",
                guests=3,
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["new_guest_count"] == 3

    def test_amended_reason_propagated(self):
        """amendment_reason from changes.reason propagates to envelope."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_006",
                check_in="2026-12-01",
                check_out="2026-12-10",
                reason="guest_request",
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["amendment_reason"] == "guest_request"

    def test_amended_missing_dates_are_none(self):
        """When no changes.dates provided, new_check_in/out are None."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_007",
                check_in=None,
                check_out=None,
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.payload["new_check_in"] is None
        assert envelope.payload["new_check_out"] is None

    def test_amended_idempotency_key_format(self):
        """BOOKING_AMENDED key: expedia:booking_amended:{event_id}."""
        envelope = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(
                event_type="reservation_modified",
                event_id="exp_a_008",
                check_in="2026-12-01",
                check_out="2026-12-10",
            ),
            tenant_id="tenant_expedia",
        )
        assert envelope.idempotency_key == "expedia:booking_amended:exp_a_008"


# ---------------------------------------------------------------------------
# T5: Cross-provider idempotency uniqueness
# ---------------------------------------------------------------------------

class TestCrossProviderIsolation:
    def test_same_event_id_different_providers_different_keys(self):
        """Same event_id on Expedia vs Booking.com → different idempotency keys."""
        exp_env = ingest_provider_event(
            provider="expedia",
            payload=_expedia_payload(event_type="reservation_created", event_id="shared_evt_001"),
            tenant_id="tenant_x",
        )
        bcom_env = ingest_provider_event(
            provider="bookingcom",
            payload={
                "event_id": "shared_evt_001",
                "reservation_id": "res_001",
                "property_id": "prop_001",
                "occurred_at": "2026-03-08T18:00:00",
                "event_type": "reservation_created",
                "tenant_id": "tenant_x",
            },
            tenant_id="tenant_x",
        )
        assert exp_env.idempotency_key != bcom_env.idempotency_key
        assert exp_env.idempotency_key.startswith("expedia:")
        assert bcom_env.idempotency_key.startswith("bookingcom:")
