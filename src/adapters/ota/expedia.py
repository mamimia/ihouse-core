from typing import Dict, Any

from .base import OTAAdapter
from .schemas import (
    NormalizedBookingEvent,
    CanonicalExternalEnvelopeInput,
)


class ExpediaAdapter(OTAAdapter):

    channel_name = "expedia"

    def normalize(
        self,
        raw_payload: Dict[str, Any],
        *,
        tenant_id: str,
        source: str,
    ) -> NormalizedBookingEvent:

        reservation_ref = raw_payload.get("reservation_id")
        property_id = raw_payload.get("property_id")

        occurred_at = (
            raw_payload.get("occurred_at")
            or raw_payload.get("modified_at")
            or raw_payload.get("created_at")
        )

        request_id = f"expedia:{reservation_ref}:{property_id}"

        return NormalizedBookingEvent(
            canonical_type="BOOKING_SYNC_INGEST",
            tenant_id=tenant_id,
            source=source,
            reservation_ref=reservation_ref,
            property_id=property_id,
            occurred_at=occurred_at,
            check_in=raw_payload.get("check_in"),
            check_out=raw_payload.get("check_out"),
            raw_event_name=raw_payload.get("event_type", "reservation_sync"),
            raw_external_id=raw_payload.get("id"),
            idempotency_request_id=request_id,
            raw_payload=raw_payload,
        )

    def to_canonical_envelope(
        self,
        normalized: NormalizedBookingEvent,
    ) -> CanonicalExternalEnvelopeInput:

        provider_status = "confirmed"

        if normalized.raw_payload.get("status") == "cancelled":
            provider_status = "cancelled"

        provider_payload = {
            "status": provider_status,
        }

        if normalized.check_in:
            provider_payload["start_date"] = normalized.check_in

        if normalized.check_out:
            provider_payload["end_date"] = normalized.check_out

        payload = {
            "provider": normalized.source,
            "external_booking_id": normalized.reservation_ref,
            "property_id": normalized.property_id,
            "provider_payload": provider_payload,
        }

        return CanonicalExternalEnvelopeInput(
            type=normalized.canonical_type,
            payload=payload,
            occurred_at=normalized.occurred_at,
            idempotency_request_id=normalized.idempotency_request_id,
        )
