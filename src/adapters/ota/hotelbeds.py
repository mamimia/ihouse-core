"""
Phase 125 — Hotelbeds Adapter (Tier 3 — EU/Global B2B Bedbank)

Hotelbeds is the world's largest B2B bedbank: it connects properties (via
property management systems) with wholesale buyers — travel agencies, tour
operators, TMCs (Travel Management Companies), and OTAs that lack direct
contracting capacity.

MARKET CONTEXT:
  - B2B bedbank, not a consumer-facing OTA like Booking.com or Airbnb
  - Headquartered in Palma de Mallorca, Spain; global coverage
  - Key markets: EU, APAC, LATAM, MENA
  - ~60,000+ hotel clients globally; connects to 65,000+ travel trade buyers
  - Revenue: ~€1.2B (2023); NASDAQ-listed parent: Hotelbeds Group
  - Transactions use EUR, GBP, USD primarily; local currencies for some markets

B2B vs. B2C PAYLOAD SEMANTICS (documented explicitly per roadmap requirement):
  B2C (Booking.com, Airbnb, etc.):
    - Guest pays gross amount to OTA
    - OTA deducts commission and remits net to property
    - total_price = gross (from guest), commission = OTA cut, net = what property receives

  B2B (Hotelbeds bedbank model):
    - Hotelbeds contracts a "net_rate" with the property in advance
    - Hotelbeds marks up that rate and sells to travel agents as "contract_price"
    - Property receives net_rate directly from Hotelbeds
    - markup_amount = contract_price - net_rate (Hotelbeds' margin)
    - Hotelbeds does NOT deduct from property — it earns by marking up
    - source_confidence = FULL when net_rate + currency present
    - total_price = contract_price (what Hotelbeds charges the buyer)
    - net_to_property = net_rate (what we actually receive)
    - ota_commission = markup_amount (Hotelbeds' markup, not a % deduction)

WEBHOOK FIELD NAMES (Hotelbeds Connect API convention):
  voucher_ref      — Hotelbeds booking reference (e.g. "HB-20260101-88991")
  hotel_code       — Property code in Hotelbeds system (maps to property_id)
  event_id         — Unique event identifier for idempotency
  event_type       — BOOKING_CONFIRMED | BOOKING_CANCELLED | BOOKING_AMENDED
  check_in         — ISO date string (YYYY-MM-DD)
  check_out        — ISO date string (YYYY-MM-DD)
  room_count       — Number of rooms booked (B2B: room-level, not guest-level)
  guest_count      — Number of guests (sum across rooms, optional in B2B context)
  contract_price   — Gross price charged to the trade buyer (string decimal)
  net_rate         — Net rate payable to property (string decimal)
  markup_amount    — Hotelbeds' margin: contract_price - net_rate (string decimal, optional)
  currency         — ISO 4217 currency code (EUR, GBP, USD, etc.)
  occurred_at      — ISO datetime string (event timestamp)
  tenant_id        — iHouse tenant identifier
  amendment        — Amendment block (BOOKING_AMENDED events only)

AMENDMENT BLOCK FIELDS:
  amendment.check_in      — new check-in date
  amendment.check_out     — new check-out date
  amendment.room_count    — new room count
  amendment.guest_count   — new guest count
  amendment.reason        — reason for amendment

FIELD MAPPING TO CANONICAL:
  voucher_ref    → reservation_id (after normalize_reservation_ref strips "HB-" prefix)
  hotel_code     → property_id
  event_id       → external_event_id
  check_in       → canonical_check_in
  check_out      → canonical_check_out
  guest_count    → canonical_guest_count (or room_count if guest_count absent)
  contract_price → canonical_total_price
  currency       → canonical_currency

PREFIX STRIPPING:
  Hotelbeds uses "HB-" prefix (e.g. "HB-20260101-88991" → "20260101-88991").
  booking_identity._PROVIDER_RULES["hotelbeds"] will handle this.

EVENT TYPES → SEMANTIC KIND:
  BOOKING_CONFIRMED  → CREATE
  BOOKING_CANCELLED  → CANCEL
  BOOKING_AMENDED    → BOOKING_AMENDED
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


class HotelbedsAdapter(OTAAdapter):
    """
    Hotelbeds OTA adapter — EU/Global B2B Bedbank (Tier 3).

    Follows standard adapter interface (Phase 35+).
    booking_id = "hotelbeds_{normalized_voucher_ref}"
    property field: hotel_code → property_id
    room/guest count: guest_count or room_count (B2B: room-level primary)
    financial field: contract_price (gross to buyer), net_rate (net to property)

    B2B semantics: property receives net_rate. Hotelbeds earns markup_amount.
    This is the inverse of B2C where the OTA deducts commission from gross.
    """

    provider = "hotelbeds"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Hotelbeds webhook payload into canonical structure.

        Hotelbeds voucher_ref may include an "HB-" prefix.
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_id       → external_event_id
          voucher_ref    → reservation_id (stripped)
          hotel_code     → property_id
          check_in       → (via schema_normalizer) canonical_check_in
          check_out      → (via schema_normalizer) canonical_check_out
          guest_count    → (via schema_normalizer) canonical_guest_count
          contract_price → (via schema_normalizer) canonical_total_price
          currency       → (via schema_normalizer) canonical_currency

        B2B note: guest_count may be absent; room_count is the primary unit.
        The schema_normalizer handles both via the hotelbeds-specific mapping.
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(
                self.provider, payload["voucher_ref"]
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
