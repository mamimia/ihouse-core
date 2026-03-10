"""
Phase 187 — Rakuten Travel Adapter (Tier 3 — Japan Market)

Rakuten Travel (楽天トラベル) is Japan's dominant domestic OTA, operated by
Rakuten Group (TSE: 4755). It is the largest accommodation booking platform
in Japan by room-nights, serving both domestic and inbound travellers.

MARKET CONTEXT:
  Rakuten Travel is a Tier 3 OTA for iHouse Core because:
  - #1 OTA in Japan by domestic market share (~40% of online bookings)
  - Essential for operators with Japanese domestic clientele
  - Strong inbound capability for travellers from East Asia (CN, KR, TW, SG)
  - Critical currency: JPY (Japanese Yen) — rarely converted by operators
  - Complements Agoda and Trip.com for overall Asia-Pacific coverage

WEBHOOK FIELD NAMES (Rakuten Travel Partner API convention):
  booking_ref         — Rakuten booking reference (e.g. "RAK-JP-20250815-001")
  hotel_code          — Property / hotel identifier in Rakuten system
  event_id            — Unique event identifier for idempotency
  event_type          — BOOKING_CREATED | BOOKING_CANCELLED | BOOKING_MODIFIED
  check_in            — ISO date string (YYYY-MM-DD)
  check_out           — ISO date string (YYYY-MM-DD)
  guest_count         — Integer guest count
  total_amount        — Gross booking amount (string decimal)
  rakuten_commission  — Rakuten platform commission (string decimal, optional)
  net_amount          — Net to partner after commission (string decimal, optional)
  currency            — ISO 4217 currency code (primarily JPY)
  occurred_at         — ISO datetime string (event timestamp)
  tenant_id           — iHouse tenant identifier
  modification        — Amendment block (BOOKING_MODIFIED events only)

AMENDMENT BLOCK FIELDS:
  modification.check_in    — new check-in date
  modification.check_out   — new check-out date
  modification.guest_count — new guest count
  modification.reason      — reason for modification

FIELD MAPPING TO CANONICAL:
  booking_ref   → reservation_id (after normalize_reservation_ref strips "RAK-" prefix)
  hotel_code    → property_id
  event_id      → external_event_id
  check_in      → canonical_check_in
  check_out     → canonical_check_out
  guest_count   → canonical_guest_count
  total_amount  → canonical_total_price
  currency      → canonical_currency

PREFIX STRIPPING:
  Rakuten booking refs use "RAK-" prefix (e.g. "RAK-JP-20250815-001" → "jp-20250815-001").
  booking_identity._PROVIDER_RULES["rakuten"] handles this.

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


class RakutenAdapter(OTAAdapter):
    """
    Rakuten Travel OTA adapter — Japan market Tier 3.

    Follows standard adapter interface (Phase 35+).
    booking_id = "rakuten_{normalized_booking_ref}"
    property field: hotel_code → property_id
    currency: primarily JPY, also USD/SGD/TWD/KRW for inbound travellers
    """

    provider = "rakuten"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Rakuten Travel webhook payload into canonical structure.

        Rakuten booking_ref uses a "RAK-" prefix
        (e.g. "RAK-JP-20250815-001" → "jp-20250815-001").
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_id      → external_event_id
          booking_ref   → reservation_id (prefix stripped)
          hotel_code    → property_id
          check_in      → (via schema_normalizer) canonical_check_in
          check_out     → (via schema_normalizer) canonical_check_out
          guest_count   → (via schema_normalizer) canonical_guest_count
          total_amount  → (via schema_normalizer) canonical_total_price
          currency      → (via schema_normalizer) canonical_currency
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(
                self.provider, payload["booking_ref"]
            ),
            property_id=payload["hotel_code"],
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
