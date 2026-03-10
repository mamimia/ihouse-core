"""
Phase 195 — Hostelworld Adapter (Tier 3 — Hostel/Budget Market)

Hostelworld (hostelworld.com) is the dominant global hostel and budget
accommodation OTA, headquartered in Dublin, Ireland. Founded 1999, it
serves 13M+ customers across 180+ countries and lists 17,000+ properties.

MARKET CONTEXT:
  Hostelworld is a Tier 3 OTA for iHouse Core because:
  - #1 global hostel OTA by market share (70%+ of online hostel bookings)
  - Essential for budget/backpacker segment properties
  - Strong European market presence (EUR, GBP dominant currencies)
  - Also critical for Southeast Asian hostel hub markets (Bangkok, Chiang Mai)
  - Complements Booking.com and Agoda for full accommodation-type coverage

WEBHOOK FIELD NAMES (Hostelworld Partner API convention):
  reservation_id      — booking reference (e.g. "HW-2025-0081234")
  property_id         — Hostelworld property code
  event_id            — unique event identifier for idempotency
  event_type          — BOOKING_CREATED | BOOKING_CANCELLED | BOOKING_MODIFIED
  check_in            — ISO date string (YYYY-MM-DD)
  check_out           — ISO date string (YYYY-MM-DD)
  guest_count         — integer guest count
  total_price         — gross booking amount (string decimal)
  hostelworld_fee     — Hostelworld commission (string decimal, optional)
  net_price           — net to property after commission (string decimal, optional)
  currency            — ISO 4217 currency code (EUR, GBP, USD, THB, etc.)
  occurred_at         — ISO datetime string (event timestamp)
  tenant_id           — iHouse tenant identifier
  amendment           — amendment block (BOOKING_MODIFIED events only)

AMENDMENT BLOCK FIELDS:
  amendment.check_in    — new check-in date
  amendment.check_out   — new check-out date
  amendment.guest_count — new guest count
  amendment.reason      — reason for modification

FIELD MAPPING TO CANONICAL:
  reservation_id → reservation_id (after normalize_reservation_ref strips "HW-")
  property_id    → property_id
  event_id       → external_event_id
  check_in       → canonical_check_in
  check_out      → canonical_check_out
  guest_count    → canonical_guest_count
  total_price    → canonical_total_price
  currency       → canonical_currency

PREFIX STRIPPING:
  Hostelworld booking refs use "HW-" prefix (e.g. "HW-2025-0081234" → "2025-0081234").
  booking_identity._PROVIDER_RULES["hostelworld"] handles this.

EVENT TYPES → SEMANTIC KIND:
  BOOKING_CREATED    → CREATE
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


class HostelworldAdapter(OTAAdapter):
    """
    Hostelworld OTA adapter — global hostel/budget market Tier 3.

    Follows standard adapter interface (Phase 35+).
    booking_id = "hostelworld_{normalized_reservation_id}"
    property field: property_id → property_id (direct, no alias)
    currency: primarily EUR/GBP/USD, also THB/AUD for regional properties
    """

    provider = "hostelworld"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Hostelworld webhook payload into canonical structure.

        Hostelworld reservation_id uses a "HW-" prefix
        (e.g. "HW-2025-0081234" → "2025-0081234").
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_id       → external_event_id
          reservation_id → reservation_id (prefix stripped)
          property_id    → property_id (direct — no alias)
          check_in       → (via schema_normalizer) canonical_check_in
          check_out      → (via schema_normalizer) canonical_check_out
          guest_count    → (via schema_normalizer) canonical_guest_count
          total_price    → (via schema_normalizer) canonical_total_price
          currency       → (via schema_normalizer) canonical_currency
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(
                self.provider, payload["reservation_id"]
            ),
            property_id=payload["property_id"],
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
            raise ValueError(
                f"Unsupported semantic kind: {classified.semantic_kind!r}"
            )

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
