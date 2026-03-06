from typing import Dict, Any

from .base import OTAAdapter
from .schemas import (
    NormalizedBookingEvent,
    CanonicalExternalEnvelopeInput,
)


class BookingComAdapter(OTAAdapter):
    channel_name = "bookingcom"

    def normalize(
        self,
        raw_payload: Dict[str, Any],
        *,
        tenant_id: str,
        source: str,
    ) -> NormalizedBookingEvent:
        raw_event_name = raw_payload.get("event_type")
        canonical_type = self._classify_raw_event(raw_event_name)

        reservation_ref = raw_payload.get("reservation_id")
        property_id = raw_payload.get("property_id")
        raw_external_id = raw_payload.get("id")
        occurred_at = (
            raw_payload.get("occurred_at")
            or raw_payload.get("modified_at")
            or raw_payload.get("created_at")
        )

        check_in = raw_payload.get("check_in")
        check_out = raw_payload.get("check_out")

        request_id = self._build_request_id(
            raw_event_name=raw_event_name,
            reservation_ref=reservation_ref,
            property_id=property_id,
            raw_external_id=raw_external_id,
        )

        return NormalizedBookingEvent(
            canonical_type=canonical_type,
            tenant_id=tenant_id,
            source=source,
            reservation_ref=reservation_ref,
            property_id=property_id,
            occurred_at=occurred_at,
            check_in=check_in,
            check_out=check_out,
            raw_event_name=raw_event_name,
            raw_external_id=raw_external_id,
            idempotency_request_id=request_id,
            raw_payload=raw_payload,
        )

    def to_canonical_envelope(
        self,
        normalized: NormalizedBookingEvent,
    ) -> CanonicalExternalEnvelopeInput:
        provider_status = "confirmed"

        if normalized.raw_event_name == "reservation_cancelled":
            provider_status = "cancelled"

        provider_payload = {
            "status": provider_status,
        }

        if normalized.check_in:
            provider_payload["start_date"] = normalized.check_in

        if normalized.check_out:
            provider_payload["end_date"] = normalized.check_out

        guest_name = normalized.raw_payload.get("guest_name")
        if guest_name:
            provider_payload["guest_name"] = guest_name

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

    def _classify_raw_event(self, raw_event_name: str) -> str:
        if raw_event_name in {"reservation_created", "reservation_cancelled"}:
            return "BOOKING_SYNC_INGEST"

        raise ValueError("unsupported_bookingcom_event")

    def _build_request_id(
        self,
        *,
        raw_event_name: str,
        reservation_ref: str,
        property_id: str,
        raw_external_id: str | None,
    ) -> str:
        if raw_external_id:
            return f"bookingcom:event:{raw_external_id}"

        return f"bookingcom:{raw_event_name}:{reservation_ref}:{property_id}"
