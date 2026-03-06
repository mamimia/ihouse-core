from __future__ import annotations

from datetime import datetime

from .base import OTAAdapter
from .schemas import (
    NormalizedBookingEvent,
    ClassifiedBookingEvent,
    CanonicalEnvelope,
)


class BookingComAdapter(OTAAdapter):

    provider = "bookingcom"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Convert Booking.com webhook payload into normalized structure.
        """

        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=payload["reservation_id"],
            property_id=payload["property_id"],
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            payload=payload,
        )

    def to_canonical_envelope(
        self,
        classified: ClassifiedBookingEvent,
    ) -> CanonicalEnvelope:

        normalized = classified.normalized

        if classified.semantic_kind == "CREATE":
            canonical_type = "BOOKING_CREATED"

        elif classified.semantic_kind == "CANCEL":
            canonical_type = "BOOKING_CANCELED"

        else:
            raise ValueError("MODIFY events are not supported")

        return CanonicalEnvelope(
            tenant_id=normalized.tenant_id,
            type=canonical_type,
            occurred_at=normalized.occurred_at,
            payload={
                "provider": self.provider,
                "reservation_id": normalized.reservation_id,
                "property_id": normalized.property_id,
                "provider_payload": normalized.payload,
            },
            idempotency_key=normalized.external_event_id,
        )
