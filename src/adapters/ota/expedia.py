from __future__ import annotations

from datetime import datetime

from .base import OTAAdapter
from .schemas import (
    NormalizedBookingEvent,
    ClassifiedBookingEvent,
    CanonicalEnvelope,
)
from .idempotency import generate_idempotency_key
from .amendment_extractor import normalize_amendment
from .financial_extractor import extract_financial_facts
from .booking_identity import normalize_reservation_ref


class ExpediaAdapter(OTAAdapter):

    provider = "expedia"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Expedia webhook payload into canonical structure.

        Expedia webhook fields used:
          event_id       — unique event identifier
          reservation_id — Expedia booking reference
          property_id    — property identifier
          occurred_at    — ISO datetime string
          tenant_id      — iHouse tenant identifier
        """

        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(self.provider, payload["reservation_id"]),
            property_id=payload["property_id"],
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            payload=payload,
            financial_facts=extract_financial_facts(self.provider, payload),
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

        elif classified.semantic_kind == "BOOKING_AMENDED":
            canonical_type = "BOOKING_AMENDED"

        else:
            raise ValueError(f"Unsupported semantic kind: {classified.semantic_kind}")

        # --- Build canonical payload ---
        canonical_payload: dict

        if canonical_type == "BOOKING_AMENDED":
            # Deterministic booking_id — same rule as BOOKING_CREATED
            booking_id = f"{self.provider}_{normalized.reservation_id}"

            # Extract provider-agnostic amendment fields (reads changes.dates + changes.guests)
            amendment = normalize_amendment(self.provider, normalized.payload)

            canonical_payload = {
                "provider": self.provider,
                "reservation_id": normalized.reservation_id,
                "property_id": normalized.property_id,
                "booking_id": booking_id,
                "new_check_in": amendment.new_check_in,
                "new_check_out": amendment.new_check_out,
                "new_guest_count": amendment.new_guest_count,
                "amendment_reason": amendment.amendment_reason,
                "provider_payload": normalized.payload,
            }
        else:
            canonical_payload = {
                "provider": self.provider,
                "reservation_id": normalized.reservation_id,
                "property_id": normalized.property_id,
                "provider_payload": normalized.payload,
            }

        return CanonicalEnvelope(
            tenant_id=normalized.tenant_id,
            type=canonical_type,
            occurred_at=normalized.occurred_at,
            payload=canonical_payload,
            idempotency_key=generate_idempotency_key(
                self.provider,
                normalized.external_event_id,
                canonical_type,
            ),
        )
