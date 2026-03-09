"""
Phase 94 — MakeMyTrip Adapter (Tier 2 — India)

MakeMyTrip (MMT) is India's dominant online travel booking platform,
widely used for hotels, flights, and holiday packages. It is a critical
channel for any property management system targeting the Indian market.

MARKET CONTEXT:
  MakeMyTrip is a Tier 2 OTA for iHouse Core because:
  - Largest OTA in India by both volume and brand recognition
  - Covers premium, mid-range, and budget properties across India
  - Required for coverage of Indian operators alongside Agoda (already present)
  - Operates across India, UAE, and Southeast Asia markets

WEBHOOK FIELD NAMES (MakeMyTrip V3 API convention):
  booking_id        — MMT primary booking reference (e.g. "MMT-IN-1234567890")
  hotel_id          — Property identifier in MMT system
  event_id          — Unique event identifier for idempotency
  event_type        — BOOKING_CONFIRMED | BOOKING_CANCELLED | BOOKING_MODIFIED
  check_in          — ISO date string (YYYY-MM-DD)
  check_out         — ISO date string (YYYY-MM-DD)
  guest_count       — Integer guest count
  order_value       — Gross booking amount (string decimal)
  mmt_commission    — MMT platform commission (string decimal)
  net_amount        — Net to property after commission (string decimal, optional)
  currency          — ISO 4217 currency code
  occurred_at       — ISO datetime string (event timestamp)
  tenant_id         — iHouse tenant identifier
  amendment         — Amendment block (present on BOOKING_MODIFIED events only)

AMENDMENT BLOCK FIELDS:
  amendment.check_in     — new check-in date
  amendment.check_out    — new check-out date
  amendment.guests       — new guest count
  amendment.reason       — reason for modification

FIELD MAPPING TO CANONICAL:
  booking_id   → reservation_id (after normalize_reservation_ref strips "MMT-" prefix)
  hotel_id     → property_id
  event_id     → external_event_id
  check_in     → canonical_check_in
  check_out    → canonical_check_out
  guest_count  → canonical_guest_count
  order_value  → canonical_total_price
  currency     → canonical_currency

PREFIX STRIPPING:
  MMT booking IDs use the "MMT-" prefix (e.g. "MMT-IN-1234567890" → "in-1234567890").
  booking_identity._PROVIDER_RULES["makemytrip"] handles this.

EVENT TYPES → SEMANTIC KIND:
  BOOKING_CONFIRMED  → CREATE
  BOOKING_CANCELLED  → CANCEL
  BOOKING_MODIFIED   → BOOKING_AMENDED
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


class MakemytripAdapter(OTAAdapter):
    """
    MakeMyTrip OTA adapter — India Tier 2.

    Follows standard adapter interface (Phase 35+).
    booking_id = "makemytrip_{normalized_booking_id}"
    property field: hotel_id → property_id
    """

    provider = "makemytrip"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize MakeMyTrip webhook payload into canonical structure.

        MMT booking_id may include a "MMT-" prefix.
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_id      → external_event_id
          booking_id    → reservation_id (stripped)
          hotel_id      → property_id
          check_in      → (via schema_normalizer) canonical_check_in
          check_out     → (via schema_normalizer) canonical_check_out
          guest_count   → (via schema_normalizer) canonical_guest_count
          order_value   → (via schema_normalizer) canonical_total_price
          currency      → (via schema_normalizer) canonical_currency
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(self.provider, payload["booking_id"]),
            property_id=payload["hotel_id"],
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
            raise ValueError(f"Unsupported semantic kind: {classified.semantic_kind!r}")

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
