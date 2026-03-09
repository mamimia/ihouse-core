"""
Phase 98 — Despegar Adapter (Tier 2 — Latin America)

Despegar.com (also operating as Decolar.com in Brazil) is the dominant online
travel agency in Latin America, with leading market positions in Argentina,
Brazil, Mexico, Chile, Colombia, and Peru.

MARKET CONTEXT:
  Despegar is a Tier 2 OTA for iHouse Core because:
  - Largest OTA native to Latin America (~$600M revenue, NYSE: DESP)
  - Critical for LATAM-focused operators and management companies
  - Covers all major LATAM currencies: ARS, BRL, MXN, CLP, COP, PEN, USD
  - Complements global OTAs (Booking.com, Expedia, Airbnb) for LATAM coverage

WEBHOOK FIELD NAMES (Despegar Partner API convention):
  reservation_code  — Despegar booking reference (e.g. "DSP-AR-9988001")
  hotel_id          — Property / hotel identifier in Despegar system
  event_id          — Unique event identifier for idempotency
  event_type        — BOOKING_CONFIRMED | BOOKING_CANCELLED | BOOKING_MODIFIED
  check_in          — ISO date string (YYYY-MM-DD)
  check_out         — ISO date string (YYYY-MM-DD)
  passenger_count   — Integer passenger/guest count (Latin American travel term)
  total_fare        — Gross booking amount (string decimal; "fare" is Despegar naming)
  despegar_fee      — Despegar platform commission (string decimal, optional)
  net_amount        — Net to partner after commission (string decimal, optional)
  currency          — ISO 4217 currency code (ARS, BRL, MXN, CLP, COP, PEN, USD)
  occurred_at       — ISO datetime string (event timestamp)
  tenant_id         — iHouse tenant identifier
  modification      — Amendment block (BOOKING_MODIFIED events only)

AMENDMENT BLOCK FIELDS:
  modification.check_in        — new check-in date
  modification.check_out       — new check-out date
  modification.passenger_count — new passenger count
  modification.reason          — reason for modification

FIELD MAPPING TO CANONICAL:
  reservation_code  → reservation_id (after normalize_reservation_ref strips "DSP-" prefix)
  hotel_id          → property_id
  event_id          → external_event_id
  check_in          → canonical_check_in
  check_out         → canonical_check_out
  passenger_count   → canonical_guest_count
  total_fare        → canonical_total_price
  currency          → canonical_currency

PREFIX STRIPPING:
  Despegar uses "DSP-" prefix (e.g. "DSP-AR-9988001" → "ar-9988001").
  booking_identity._PROVIDER_RULES["despegar"] handles this.

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


class DespegarAdapter(OTAAdapter):
    """
    Despegar OTA adapter — Latin America Tier 2.

    Follows standard adapter interface (Phase 35+).
    booking_id = "despegar_{normalized_reservation_code}"
    property field: hotel_id → property_id
    guest count field: passenger_count (LATAM travel terminology)
    financial field: total_fare (Despegar's naming convention)
    """

    provider = "despegar"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Despegar webhook payload into canonical structure.

        Despegar reservation_code may include a "DSP-" prefix.
        normalize_reservation_ref strips the prefix and lowercases.

        Fields:
          event_id          → external_event_id
          reservation_code  → reservation_id (stripped)
          hotel_id          → property_id
          check_in          → (via schema_normalizer) canonical_check_in
          check_out         → (via schema_normalizer) canonical_check_out
          passenger_count   → (via schema_normalizer) canonical_guest_count
          total_fare        → (via schema_normalizer) canonical_total_price
          currency          → (via schema_normalizer) canonical_currency
        """
        enriched = normalize_schema(self.provider, payload)
        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(
                self.provider, payload["reservation_code"]
            ),
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
