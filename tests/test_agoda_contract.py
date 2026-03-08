"""
Phase 55 Contract Tests: Agoda Adapter

Verifies that the Agoda OTA adapter correctly handles:
- BOOKING_CREATED (booking.created)
- BOOKING_CANCELED (booking.cancelled)
- BOOKING_AMENDED (booking.modified)

All tests are unit/contract — no live Supabase required.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import pytest

from adapters.ota.service import ingest_provider_event
from adapters.ota.agoda import AgodaAdapter


def _agoda_payload(
    *,
    event_id: str = "agoda_evt_001",
    event_type: str = "booking.created",
    booking_ref: str = "agoda_ref_001",
    property_id: str = "agoda_prop_001",
    tenant_id: str = "tenant_agoda",
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    num_guests: Optional[int] = None,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "booking_ref": booking_ref,
        "property_id": property_id,
        "occurred_at": "2026-03-08T18:00:00",
        "event_type": event_type,
        "tenant_id": tenant_id,
    }
    if any(v is not None for v in [check_in_date, check_out_date, num_guests, reason]):
        modification: Dict[str, Any] = {}
        if check_in_date is not None:
            modification["check_in_date"] = check_in_date
        if check_out_date is not None:
            modification["check_out_date"] = check_out_date
        if num_guests is not None:
            modification["num_guests"] = num_guests
        if reason is not None:
            modification["reason"] = reason
        payload["modification"] = modification
    return payload


adapter = AgodaAdapter()


class TestAgodaNormalize:
    def test_normalize_maps_booking_ref_to_reservation_id(self):
        """normalize() maps Agoda booking_ref to canonical reservation_id."""
        payload = _agoda_payload(booking_ref="agoda_ref_xyz")
        normalized = adapter.normalize(payload)
        assert normalized.reservation_id == "agoda_ref_xyz"

    def test_normalize_maps_all_core_fields(self):
        """normalize() correctly maps all required fields."""
        payload = _agoda_payload(event_id="agoda_n_001")
        normalized = adapter.normalize(payload)
        assert normalized.provider == "agoda"
        assert normalized.external_event_id == "agoda_n_001"
        assert normalized.tenant_id == "tenant_agoda"
        assert isinstance(normalized.occurred_at, datetime)

    def test_normalize_payload_preserved(self):
        """Original payload dict is preserved."""
        payload = _agoda_payload()
        normalized = adapter.normalize(payload)
        assert normalized.payload == payload


class TestAgodaBookingCreated:
    def test_created_envelope_type(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(event_type="booking.created", event_id="agoda_c_001"),
            tenant_id="tenant_agoda",
        )
        assert envelope.type == "BOOKING_CREATED"

    def test_created_idempotency_key_format(self):
        """BOOKING_CREATED key: agoda:booking_created:{event_id}."""
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(event_type="booking.created", event_id="agoda_c_002"),
            tenant_id="tenant_agoda",
        )
        assert envelope.idempotency_key == "agoda:booking_created:agoda_c_002"

    def test_created_payload_fields(self):
        """BOOKING_CREATED payload carries provider, reservation_id, property_id."""
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.created",
                event_id="agoda_c_003",
                booking_ref="agoda_ref_001",
                property_id="agoda_prop_001",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["provider"] == "agoda"
        assert envelope.payload["reservation_id"] == "agoda_ref_001"
        assert envelope.payload["property_id"] == "agoda_prop_001"

    def test_created_tenant_propagated(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(event_type="booking.created", event_id="agoda_c_004"),
            tenant_id="tenant_abc",
        )
        assert envelope.tenant_id == "tenant_abc"


class TestAgodaBookingCanceled:
    def test_canceled_envelope_type(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(event_type="booking.cancelled", event_id="agoda_x_001"),
            tenant_id="tenant_agoda",
        )
        assert envelope.type == "BOOKING_CANCELED"

    def test_canceled_key_format(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(event_type="booking.canceled", event_id="agoda_x_002"),
            tenant_id="tenant_agoda",
        )
        assert envelope.idempotency_key == "agoda:booking_canceled:agoda_x_002"


class TestAgodaBookingAmended:
    def test_amended_envelope_type(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_001",
                check_in_date="2026-11-01",
                check_out_date="2026-11-07",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.type == "BOOKING_AMENDED"

    def test_amended_booking_id(self):
        """booking_id = agoda_{booking_ref}."""
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_002",
                booking_ref="agoda_ref_999",
                check_in_date="2026-11-01",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["booking_id"] == "agoda_agoda_ref_999"

    def test_amended_check_in_propagated(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_003",
                check_in_date="2026-12-01",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["new_check_in"] == "2026-12-01"

    def test_amended_check_out_propagated(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_004",
                check_out_date="2026-12-10",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["new_check_out"] == "2026-12-10"

    def test_amended_guest_count_propagated(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_005",
                check_in_date="2026-12-01",
                num_guests=5,
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["new_guest_count"] == 5

    def test_amended_reason_propagated(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_006",
                reason="date_change",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["amendment_reason"] == "date_change"

    def test_amended_missing_fields_are_none(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(event_type="booking.modified", event_id="agoda_a_007"),
            tenant_id="tenant_agoda",
        )
        assert envelope.payload["new_check_in"] is None
        assert envelope.payload["new_check_out"] is None

    def test_amended_idempotency_key_format(self):
        envelope = ingest_provider_event(
            provider="agoda",
            payload=_agoda_payload(
                event_type="booking.modified",
                event_id="agoda_a_008",
                check_in_date="2026-12-01",
            ),
            tenant_id="tenant_agoda",
        )
        assert envelope.idempotency_key == "agoda:booking_amended:agoda_a_008"


class TestCrossProviderFourWay:
    def test_same_event_id_four_providers_unique_keys(self):
        """Same event_id across all 4 providers → 4 unique idempotency keys."""
        providers_payloads = [
            ("agoda", _agoda_payload(event_type="booking.created", event_id="shared_001")),
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
        assert len(keys) == 4
