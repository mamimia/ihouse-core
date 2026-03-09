"""
Phase 85 — Google Vacation Rentals (GVR) Adapter

ARCHITECTURAL NOTE — How GVR Differs from Classic OTAs:
========================================================
Classic OTAs (Booking.com, Airbnb, Expedia, Agoda, Trip.com, Vrbo) are
marketplaces: they own the guest relationship, process payment, and send
webhooks when reservations are created/amended/canceled.

Google Vacation Rentals is a DISTRIBUTION SURFACE, not a marketplace:
- GVR indexes property listings and redirects guests to the property manager's
  booking engine or to a connected OTA channel (e.g. Booking.com, Vrbo).
- GVR does NOT process payments directly in the standard integration mode.
- Bookings made via GVR arrive through a "connected channel" (another OTA),
  or directly via the property manager's own system.
- GVR sends structured webhook notifications when a booking originating from
  a GVR redirect is confirmed, modified, or canceled.

Implications for iHouse Core:
- The adapter pattern is IDENTICAL (normalize → classify → to_canonical_envelope).
- Field naming differs: GVR uses `gvr_booking_id` (not `reservation_id`),
  `property_id` (standard), and financial data is forwarded from the
  connected booking source.
- The `source` in event_log will be "gvr" to distinguish GVR-originated
  bookings from the same property appearing via other channels.
- booking_id = "gvr_{normalized_gvr_booking_id}" — Phase 36 invariant applies.

GVR webhook fields:
  event_id        — unique event identifier
  gvr_booking_id  — Google's booking reference (distinct from connected OTA ref)
  property_id     — property identifier (standard field)
  occurred_at     — ISO datetime string
  event_type      — semantic event type
  tenant_id       — iHouse tenant identifier
  connected_ota   — which OTA channel the booking came through (optional)

Financial fields:
  booking_value   — gross booking amount as reported by GVR
  currency        — ISO 4217 currency code
  google_fee      — Google's platform fee (if applicable)
  net_amount      — net to property after google_fee (if calculable)
"""
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
from .schema_normalizer import normalize_schema


class GVRAdapter(OTAAdapter):
    """
    Google Vacation Rentals adapter.

    Follows the standard OTA adapter interface (Phase 35+).
    See module docstring for GVR-specific architectural notes.

    booking_id = "gvr_{normalized_gvr_booking_id}"
    property_id uses standard field name 'property_id'.
    """

    provider = "gvr"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize GVR webhook payload into canonical structure.

        GVR webhook fields:
          event_id       — unique event identifier
          gvr_booking_id — GVR booking reference (used as reservation_id)
          property_id    — property identifier
          occurred_at    — ISO datetime string
          event_type     — semantic event type
          tenant_id      — iHouse tenant identifier
          connected_ota  — optional: which OTA channel surfaced this booking
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(self.provider, payload["gvr_booking_id"]),
            property_id=payload["property_id"],      # Standard field — same as bookingcom/expedia
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            payload=enriched,
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
            booking_id = f"{self.provider}_{normalized.reservation_id}"
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
                # GVR-specific: preserve connected_ota for routing visibility
                "connected_ota": normalized.payload.get("connected_ota"),
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
