"""
Phase 96 — Klook Adapter (Tier 2 — Asia)

Klook is Asia's leading online travel activities and experiences platform,
operating across Hong Kong, Singapore, South Korea, Japan, Taiwan, and
Southeast Asia. It is a critical channel for activity and tour operators
across the Asia-Pacific region.

MARKET CONTEXT:
  Klook is a Tier 2 OTA for iHouse Core because:
  - Largest activities/experiences platform in Asia-Pacific
  - Strong penetration in HK, SG, KR, JP, TW, TH, and wider SEA
  - Required for operators offering tours, activities, and day experiences
  - Complements hotel/room-focused OTAs (Agoda, Trip.com, MakeMyTrip)

WEBHOOK FIELD NAMES (Klook Partner API v4 convention):
  booking_ref       — Klook primary booking reference (e.g. "KL-ACTBK-12345678")
  activity_id       — Activity / property identifier in Klook system
  event_id          — Unique event identifier for idempotency
  event_type        — BOOKING_CONFIRMED | BOOKING_CANCELLED | BOOKING_MODIFIED
  travel_date       — ISO date string (YYYY-MM-DD) — activity start date
  end_date          — ISO date string (YYYY-MM-DD) — activity end date (if multi-day)
  participants      — Integer participant count (= guest_count canonical)
  booking_amount    — Gross booking amount (string decimal)
  klook_commission  — Klook platform commission (string decimal, optional)
  net_payout        — Net to partner after commission (string decimal, optional)
  currency          — ISO 4217 currency code
  occurred_at       — ISO datetime string (event timestamp)
  tenant_id         — iHouse tenant identifier
  modification      — Amendment block (present on BOOKING_MODIFIED events only)

AMENDMENT BLOCK FIELDS:
  modification.travel_date   — new activity start date
  modification.end_date      — new activity end date
  modification.participants  — new participant count
  modification.reason        — reason for modification

FIELD MAPPING TO CANONICAL:
  booking_ref       → reservation_id (after normalize_reservation_ref strips "KL-" prefix)
  activity_id       → property_id
  event_id          → external_event_id
  travel_date       → canonical_check_in
  end_date          → canonical_check_out
  participants      → canonical_guest_count
  booking_amount    → canonical_total_price
  currency          → canonical_currency

PREFIX STRIPPING:
  Klook booking refs use the "KL-" prefix (e.g. "KL-ACTBK-12345678" → "actbk-12345678").
  booking_identity._PROVIDER_RULES["klook"] handles this.

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


class KlookAdapter(OTAAdapter):
    """
    Klook OTA adapter — Asia activities/tours Tier 2.

    Follows standard adapter interface (Phase 35+).
    booking_id = "klook_{normalized_booking_ref}"
    property field: activity_id → property_id
    """

    provider = "klook"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Klook webhook payload into canonical structure.

        Klook booking_ref may include a "KL-" prefix.
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_id      → external_event_id
          booking_ref   → reservation_id (stripped)
          activity_id   → property_id
          travel_date   → (via schema_normalizer) canonical_check_in
          end_date      → (via schema_normalizer) canonical_check_out
          participants  → (via schema_normalizer) canonical_guest_count
          booking_amount → (via schema_normalizer) canonical_total_price
          currency      → (via schema_normalizer) canonical_currency
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(self.provider, payload["booking_ref"]),
            property_id=payload["activity_id"],
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
