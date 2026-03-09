"""
Phase 88 — Traveloka Adapter

Traveloka is the dominant online travel agency for Southeast Asia,
with primary strength in Indonesia, Thailand, Vietnam, Malaysia, and the Philippines.

MARKET CONTEXT:
  Traveloka is a Tier 1.5 OTA for iHouse Core because:
  - Largest OTA in Southeast Asia by market share
  - Critical for operators with properties in Thailand, Bali, and regional SE Asia
  - Required for full regional coverage alongside Agoda (Booking Holdings) and Trip.com

WEBHOOK FIELD NAMES (Traveloka v2 API convention):
  booking_code      — Traveloka's primary booking reference (e.g. "TV-12345678")
  property_code     — Property identifier in Traveloka system
  check_in_date     — ISO date string (YYYY-MM-DD)
  check_out_date    — ISO date string (YYYY-MM-DD)
  num_guests        — Integer guest count
  booking_total     — Gross booking amount (string decimal)
  traveloka_fee     — Traveloka platform commission (string decimal, optional)
  net_payout        — Net to property after commission (string decimal, optional)
  currency_code     — ISO 4217 currency code
  event_type        — Traveloka event type (BOOKING_CONFIRMED / BOOKING_CANCELLED / BOOKING_MODIFIED)
  event_reference   — Unique event identifier for idempotency
  tenant_id         — iHouse tenant identifier
  modification      — Amendment block (present on BOOKING_MODIFIED events only)

BOOKING_MODIFIED amendment block fields:
  modification.check_in_date
  modification.check_out_date
  modification.num_guests
  modification.modification_reason

FIELD MAPPING TO CANONICAL:
  booking_code   → reservation_id (after normalize_reservation_ref strips "TV-" prefix)
  property_code  → property_id
  check_in_date  → canonical_check_in
  check_out_date → canonical_check_out
  num_guests     → canonical_guest_count
  booking_total  → canonical_total_price
  currency_code  → canonical_currency

PREFIX STRIPPING:
  Traveloka booking codes are prefixed with "TV-" (e.g. "TV-12345678").
  The strip rule removes the "TV-" prefix to produce the stable core reference.
  booking_identity._PROVIDER_RULES["traveloka"] handles this.

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


class TravelokaAdapter(OTAAdapter):
    """
    Traveloka OTA adapter — Southeast Asia Tier 1.5.

    Follows standard adapter interface (Phase 35+).
    booking_id = "traveloka_{normalized_booking_code}"
    property field: property_code → property_id
    """

    provider = "traveloka"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Traveloka webhook payload into canonical structure.

        Traveloka booking_code may include a "TV-" prefix.
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_reference  → external_event_id
          booking_code     → reservation_id (stripped)
          property_code    → property_id
          check_in_date    → (via schema_normalizer) canonical_check_in
          check_out_date   → (via schema_normalizer) canonical_check_out
          num_guests       → (via schema_normalizer) canonical_guest_count
          booking_total    → (via schema_normalizer) canonical_total_price
          currency_code    → (via schema_normalizer) canonical_currency
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_reference"],
            reservation_id=normalize_reservation_ref(self.provider, payload["booking_code"]),
            property_id=payload["property_code"],
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
