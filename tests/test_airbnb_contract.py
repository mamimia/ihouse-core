"""
Phase 54 Contract Tests: Airbnb Adapter

Verifies that the Airbnb OTA adapter correctly handles:
- BOOKING_CREATED (reservation_create)
- BOOKING_CANCELED (reservation_cancel)
- BOOKING_AMENDED (alteration_create)

All tests are unit/contract — no live Supabase required.

Run:
    cd "/Users/clawadmin/Antigravity Proj/ihouse-core"
    source .venv/bin/activate
    PYTHONPATH=src python3 -m pytest tests/test_airbnb_contract.py -v
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pytest

from adapters.ota.service import ingest_provider_event
from adapters.ota.airbnb import AirbnbAdapter
from adapters.ota.schemas import NormalizedBookingEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _airbnb_payload(
    *,
    event_id: str = "airbnb_evt_001",
    event_type: str = "reservation_create",
    reservation_id: str = "airbnb_res_001",
    listing_id: str = "airbnb_listing_001",
    tenant_id: str = "tenant_airbnb",
    new_check_in: Optional[str] = None,
    new_check_out: Optional[str] = None,
    guest_count: Optional[int] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a minimal Airbnb webhook payload."""
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "reservation_id": reservation_id,
        "listing_id": listing_id,
        "occurred_at": "2026-03-08T18:00:00",
        "event_type": event_type,
        "tenant_id": tenant_id,
    }
    # Airbnb amendment data lives under 'alteration'
    if any(v is not None for v in [new_check_in, new_check_out, guest_count, reason]):
        alteration: Dict[str, Any] = {}
        if new_check_in is not None:
            alteration["new_check_in"] = new_check_in
        if new_check_out is not None:
            alteration["new_check_out"] = new_check_out
        if guest_count is not None:
            alteration["guest_count"] = guest_count
        if reason is not None:
            alteration["reason"] = reason
        payload["alteration"] = alteration
    return payload


adapter = AirbnbAdapter()


# ---------------------------------------------------------------------------
# T1: normalize() — field mapping (listing_id → property_id)
# ---------------------------------------------------------------------------

class TestAirbnbNormalize:
    def test_normalize_maps_listing_id_to_property_id(self):
        """normalize() maps Airbnb listing_id to canonical property_id."""
        payload = _airbnb_payload(listing_id="listing_abc")
        normalized = adapter.normalize(payload)
        assert normalized.property_id == "listing_abc"

    def test_normalize_maps_all_core_fields(self):
        """normalize() correctly maps all required fields."""
        payload = _airbnb_payload(event_id="airbnb_n_001", reservation_id="res_n_001")
        normalized = adapter.normalize(payload)

        assert normalized.provider == "airbnb"
        assert normalized.external_event_id == "airbnb_n_001"
        assert normalized.reservation_id == "res_n_001"
        assert normalized.tenant_id == "tenant_airbnb"
        assert isinstance(normalized.occurred_at, datetime)

    def test_normalize_payload_preserved(self):
        """Original payload dict is preserved in normalized.payload."""
        payload = _airbnb_payload()
        normalized = adapter.normalize(payload)
        assert normalized.payload == payload


# ---------------------------------------------------------------------------
# T2: BOOKING_CREATED via full pipeline
# ---------------------------------------------------------------------------

class TestAirbnbBookingCreated:
    def test_created_envelope_type(self):
        """reservation_create → BOOKING_CREATED canonical envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(event_type="reservation_create", event_id="airbnb_c_001"),
            tenant_id="tenant_airbnb",
        )
        assert envelope.type == "BOOKING_CREATED"

    def test_created_idempotency_key_format(self):
        """BOOKING_CREATED key: airbnb:booking_created:{event_id}."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(event_type="created", event_id="airbnb_c_002"),
            tenant_id="tenant_airbnb",
        )
        assert envelope.idempotency_key == "airbnb:booking_created:airbnb_c_002"

    def test_created_property_id_from_listing_id(self):
        """property_id in canonical payload comes from Airbnb listing_id."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="reservation_create",
                event_id="airbnb_c_003",
                listing_id="listing_xyz",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["property_id"] == "listing_xyz"

    def test_created_tenant_propagated(self):
        """tenant_id propagates to canonical envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(event_type="reservation_create", event_id="airbnb_c_004"),
            tenant_id="tenant_abc",
        )
        assert envelope.tenant_id == "tenant_abc"


# ---------------------------------------------------------------------------
# T3: BOOKING_CANCELED via full pipeline
# ---------------------------------------------------------------------------

class TestAirbnbBookingCanceled:
    def test_canceled_envelope_type(self):
        """reservation_cancel → BOOKING_CANCELED canonical envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(event_type="reservation_cancel", event_id="airbnb_x_001"),
            tenant_id="tenant_airbnb",
        )
        assert envelope.type == "BOOKING_CANCELED"

    def test_canceled_idempotency_key_format(self):
        """BOOKING_CANCELED key: airbnb:booking_canceled:{event_id}."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(event_type="cancelled", event_id="airbnb_x_002"),
            tenant_id="tenant_airbnb",
        )
        assert envelope.idempotency_key == "airbnb:booking_canceled:airbnb_x_002"


# ---------------------------------------------------------------------------
# T4: BOOKING_AMENDED via full pipeline
# ---------------------------------------------------------------------------

class TestAirbnbBookingAmended:
    def test_amended_envelope_type(self):
        """alteration_create → BOOKING_AMENDED canonical envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_001",
                new_check_in="2026-11-01",
                new_check_out="2026-11-07",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.type == "BOOKING_AMENDED"

    def test_amended_booking_id(self):
        """booking_id = airbnb_{reservation_id}."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="reservation_modified",
                event_id="airbnb_a_002",
                reservation_id="airbnb_res_999",
                new_check_in="2026-11-01",
                new_check_out="2026-11-07",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["booking_id"] == "airbnb_airbnb_res_999"

    def test_amended_check_in_propagated(self):
        """new_check_in from alteration.new_check_in propagates to envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_003",
                new_check_in="2026-12-01",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["new_check_in"] == "2026-12-01"

    def test_amended_check_out_propagated(self):
        """new_check_out from alteration.new_check_out propagates to envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_004",
                new_check_out="2026-12-10",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["new_check_out"] == "2026-12-10"

    def test_amended_guest_count_propagated(self):
        """new_guest_count from alteration.guest_count propagates to envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_005",
                new_check_in="2026-12-01",
                guest_count=4,
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["new_guest_count"] == 4

    def test_amended_reason_propagated(self):
        """amendment_reason from alteration.reason propagates to envelope."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_006",
                new_check_in="2026-12-01",
                reason="travel_change",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["amendment_reason"] == "travel_change"

    def test_amended_missing_fields_are_none(self):
        """When no alteration fields provided, amendment fields are None."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_007",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.payload["new_check_in"] is None
        assert envelope.payload["new_check_out"] is None
        assert envelope.payload["new_guest_count"] is None

    def test_amended_idempotency_key_format(self):
        """BOOKING_AMENDED key: airbnb:booking_amended:{event_id}."""
        envelope = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(
                event_type="alteration_create",
                event_id="airbnb_a_008",
                new_check_in="2026-12-01",
            ),
            tenant_id="tenant_airbnb",
        )
        assert envelope.idempotency_key == "airbnb:booking_amended:airbnb_a_008"


# ---------------------------------------------------------------------------
# T5: Cross-provider idempotency uniqueness — all 3 providers
# ---------------------------------------------------------------------------

class TestCrossProviderIsolation:
    def test_same_event_id_three_providers_yield_unique_keys(self):
        """Same event_id across airbnb/expedia/bookingcom → 3 unique keys."""
        airbnb_env = ingest_provider_event(
            provider="airbnb",
            payload=_airbnb_payload(event_type="reservation_create", event_id="shared_001"),
            tenant_id="tenant_x",
        )
        expedia_env = ingest_provider_event(
            provider="expedia",
            payload={
                "event_id": "shared_001",
                "reservation_id": "res_001",
                "property_id": "prop_001",
                "occurred_at": "2026-03-08T18:00:00",
                "event_type": "reservation_created",
                "tenant_id": "tenant_x",
            },
            tenant_id="tenant_x",
        )
        bcom_env = ingest_provider_event(
            provider="bookingcom",
            payload={
                "event_id": "shared_001",
                "reservation_id": "res_001",
                "property_id": "prop_001",
                "occurred_at": "2026-03-08T18:00:00",
                "event_type": "reservation_created",
                "tenant_id": "tenant_x",
            },
            tenant_id="tenant_x",
        )
        keys = {airbnb_env.idempotency_key, expedia_env.idempotency_key, bcom_env.idempotency_key}
        assert len(keys) == 3
        assert airbnb_env.idempotency_key.startswith("airbnb:")
        assert expedia_env.idempotency_key.startswith("expedia:")
        assert bcom_env.idempotency_key.startswith("bookingcom:")
