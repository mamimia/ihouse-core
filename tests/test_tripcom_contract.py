"""
Phase 56 Contract Tests: Trip.com Adapter

Verifies that the Trip.com OTA adapter correctly handles:
- BOOKING_CREATED (order_created)
- BOOKING_CANCELED (order_cancelled)
- BOOKING_AMENDED (order_modified)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pytest

from adapters.ota.service import ingest_provider_event
from adapters.ota.tripcom import TripComAdapter


def _tripcom_payload(
    *,
    event_id: str = "tripcom_evt_001",
    event_type: str = "order_created",
    order_id: str = "tripcom_ord_001",
    hotel_id: str = "tripcom_hotel_001",
    tenant_id: str = "tenant_tripcom",
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
    guests: Optional[int] = None,
    remark: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "order_id": order_id,
        "hotel_id": hotel_id,
        "occurred_at": "2026-03-08T18:00:00",
        "event_type": event_type,
        "tenant_id": tenant_id,
    }
    if any(v is not None for v in [check_in, check_out, guests, remark]):
        changes: Dict[str, Any] = {}
        if check_in is not None:
            changes["check_in"] = check_in
        if check_out is not None:
            changes["check_out"] = check_out
        if guests is not None:
            changes["guests"] = guests
        if remark is not None:
            changes["remark"] = remark
        payload["changes"] = changes
    return payload


adapter = TripComAdapter()


class TestTripComNormalize:
    def test_normalize_maps_order_id_to_reservation_id(self):
        payload = _tripcom_payload(order_id="ord_xyz")
        normalized = adapter.normalize(payload)
        assert normalized.reservation_id == "ord_xyz"

    def test_normalize_maps_hotel_id_to_property_id(self):
        payload = _tripcom_payload(hotel_id="hotel_abc")
        normalized = adapter.normalize(payload)
        assert normalized.property_id == "hotel_abc"

    def test_normalize_maps_all_core_fields(self):
        payload = _tripcom_payload(event_id="tripcom_n_001")
        normalized = adapter.normalize(payload)
        assert normalized.provider == "tripcom"
        assert normalized.external_event_id == "tripcom_n_001"
        assert normalized.tenant_id == "tenant_tripcom"
        assert isinstance(normalized.occurred_at, datetime)

    def test_normalize_payload_preserved(self):
        payload = _tripcom_payload()
        normalized = adapter.normalize(payload)
        assert normalized.payload == payload


class TestTripComBookingCreated:
    def test_created_envelope_type(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(event_type="order_created", event_id="tripcom_c_001"),
            tenant_id="tenant_tripcom",
        )
        assert envelope.type == "BOOKING_CREATED"

    def test_created_idempotency_key_format(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(event_type="order_created", event_id="tripcom_c_002"),
            tenant_id="tenant_tripcom",
        )
        assert envelope.idempotency_key == "tripcom:booking_created:tripcom_c_002"

    def test_created_payload_fields(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_created",
                event_id="tripcom_c_003",
                order_id="ord_001",
                hotel_id="hotel_001",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["provider"] == "tripcom"
        assert envelope.payload["reservation_id"] == "ord_001"
        assert envelope.payload["property_id"] == "hotel_001"

    def test_created_tenant_propagated(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(event_type="order_created", event_id="tripcom_c_004"),
            tenant_id="tenant_xyz",
        )
        assert envelope.tenant_id == "tenant_xyz"


class TestTripComBookingCanceled:
    def test_canceled_envelope_type(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(event_type="order_cancelled", event_id="tripcom_x_001"),
            tenant_id="tenant_tripcom",
        )
        assert envelope.type == "BOOKING_CANCELED"

    def test_canceled_key_format(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(event_type="order_canceled", event_id="tripcom_x_002"),
            tenant_id="tenant_tripcom",
        )
        assert envelope.idempotency_key == "tripcom:booking_canceled:tripcom_x_002"


class TestTripComBookingAmended:
    def test_amended_envelope_type(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_001",
                check_in="2026-11-01",
                check_out="2026-11-07",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.type == "BOOKING_AMENDED"

    def test_amended_booking_id(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_002",
                order_id="ord_999",
                check_in="2026-11-01",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["booking_id"] == "tripcom_ord_999"

    def test_amended_check_in_propagated(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_003",
                check_in="2026-12-01",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["new_check_in"] == "2026-12-01"

    def test_amended_check_out_propagated(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_004",
                check_out="2026-12-10",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["new_check_out"] == "2026-12-10"

    def test_amended_guests_propagated(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_005",
                check_in="2026-12-01",
                guests=3,
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["new_guest_count"] == 3

    def test_amended_remark_propagated(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_006",
                remark="date_adjustment",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["amendment_reason"] == "date_adjustment"

    def test_amended_missing_fields_are_none(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(event_type="order_modified", event_id="tripcom_a_007"),
            tenant_id="tenant_tripcom",
        )
        assert envelope.payload["new_check_in"] is None
        assert envelope.payload["new_check_out"] is None

    def test_amended_idempotency_key_format(self):
        envelope = ingest_provider_event(
            provider="tripcom",
            payload=_tripcom_payload(
                event_type="order_modified",
                event_id="tripcom_a_008",
                check_in="2026-12-01",
            ),
            tenant_id="tenant_tripcom",
        )
        assert envelope.idempotency_key == "tripcom:booking_amended:tripcom_a_008"


class TestCrossProviderFiveWay:
    def test_same_event_id_five_providers_unique_keys(self):
        """Same event_id across all 5 providers → 5 unique idempotency keys."""
        providers_payloads = [
            ("tripcom", _tripcom_payload(event_type="order_created", event_id="shared_001")),
            ("agoda", {"event_id": "shared_001", "booking_ref": "ref", "property_id": "prop",
                       "occurred_at": "2026-03-08T18:00:00", "event_type": "booking.created",
                       "tenant_id": "t"}),
            ("airbnb", {"event_id": "shared_001", "reservation_id": "res", "listing_id": "prop",
                        "occurred_at": "2026-03-08T18:00:00", "event_type": "reservation_create",
                        "tenant_id": "t"}),
            ("expedia", {"event_id": "shared_001", "reservation_id": "res", "property_id": "prop",
                         "occurred_at": "2026-03-08T18:00:00", "event_type": "reservation_created",
                         "tenant_id": "t"}),
            ("bookingcom", {"event_id": "shared_001", "reservation_id": "res", "property_id": "prop",
                            "occurred_at": "2026-03-08T18:00:00", "event_type": "reservation_created",
                            "tenant_id": "t"}),
        ]
        keys = set()
        for provider, payload in providers_payloads:
            env = ingest_provider_event(provider=provider, payload=payload, tenant_id="t")
            keys.add(env.idempotency_key)
        assert len(keys) == 5
        prefixes = {k.split(":")[0] for k in keys}
        assert prefixes == {"tripcom", "agoda", "airbnb", "expedia", "bookingcom"}
