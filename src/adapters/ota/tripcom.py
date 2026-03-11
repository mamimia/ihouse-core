"""
Phase 238 — Ctrip / Trip.com Enhanced Adapter (Tier 2 — China Market)

Trip.com (携程旅行) is China's largest OTA, operating globally under the
Trip.com Group brand (NASDAQ: TCOM). The domestic Ctrip brand dominates
Chinese-origin travel bookings and has specific webhook conventions.

MARKET CONTEXT:
  Trip.com / Ctrip is elevated to Tier 2 for iHouse Core because:
  - #1 OTA in China (~60% of outbound Chinese travel bookings)
  - Significant share in Southeast Asia (Thailand, Singapore, Japan)
  - Primary currency: CNY (Chinese Yuan) — operators often see CNY payouts
  - Guest names frequently in Chinese characters only (汉字)
  - Ctrip-specific cancellation policies with coded reason fields
  - Dual brand: "Trip.com" internationally, "Ctrip" (携程) domestically

WEBHOOK FIELD NAMES (Trip.com / Ctrip Partner API convention):
  event_id            — unique event identifier for idempotency
  order_id            — Trip.com order reference (legacy, numeric)
  booking_ref         — Ctrip booking reference (e.g. "CTRIP-CN-20260301-001")
  hotel_id            — property / hotel identifier in Trip.com system
  event_type          — BOOKING_CREATED | BOOKING_CANCELLED | BOOKING_MODIFIED
  check_in            — ISO date string (YYYY-MM-DD)
  check_out           — ISO date string (YYYY-MM-DD)
  guest_count         — integer guest count
  guest_name          — guest name in Latin/ASCII (may be absent)
  guest_name_cn       — guest name in Chinese characters (汉字)
  total_amount        — gross booking amount (string decimal)
  tripcom_commission  — platform commission (string decimal, optional)
  net_amount          — net to partner after commission (string decimal, optional)
  currency            — ISO 4217 currency code (primarily CNY, also THB/USD)
  occurred_at         — ISO datetime string (event timestamp)
  tenant_id           — iHouse tenant identifier
  cancellation_code   — Ctrip cancel reason: NC (no charge), FC (full charge), PC (partial charge)
  modification        — amendment block (BOOKING_MODIFIED events only)

AMENDMENT BLOCK FIELDS:
  modification.check_in       — new check-in date
  modification.check_out      — new check-out date
  modification.guest_count    — new guest count
  modification.reason         — reason for modification

CANCELLATION CODES (Ctrip-specific):
  NC → no_charge      (free cancellation window)
  FC → full_charge    (non-refundable or past deadline)
  PC → partial_charge (partial penalty applies)

FIELD MAPPING TO CANONICAL:
  booking_ref / order_id → reservation_id (after prefix stripping)
  hotel_id               → property_id
  event_id               → external_event_id
  check_in               → canonical_check_in
  check_out              → canonical_check_out
  guest_count            → canonical_guest_count
  total_amount           → canonical_total_price
  currency               → canonical_currency (defaults CNY)

PREFIX STRIPPING:
  Ctrip booking refs use "CTRIP-" prefix (e.g. "CTRIP-CN-20260301-001" → "cn-20260301-001").
  Legacy Trip.com uses "TC-" prefix (e.g. "TC-12345" → "12345").
  booking_identity._PROVIDER_RULES["tripcom"] handles both.

EVENT TYPES → SEMANTIC KIND:
  BOOKING_CREATED    → CREATE
  BOOKING_CANCELLED  → CANCEL
  BOOKING_MODIFIED   → BOOKING_AMENDED
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

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


# ---------------------------------------------------------------------------
# Ctrip-specific helpers
# ---------------------------------------------------------------------------

_CTRIP_CANCEL_CODES: Dict[str, str] = {
    "NC": "no_charge",
    "FC": "full_charge",
    "PC": "partial_charge",
}


def resolve_ctrip_cancel_reason(code: Optional[str]) -> str:
    """Map Ctrip cancellation code to human-readable reason."""
    if not code:
        return "unknown"
    return _CTRIP_CANCEL_CODES.get(code.upper(), f"ctrip_code_{code}")


def romanize_guest_name(
    guest_name: Optional[str] = None,
    guest_name_cn: Optional[str] = None,
    fallback: str = "Guest",
) -> str:
    """
    Return the best available guest name in Latin characters.

    Priority:
      1. guest_name (ASCII / romanized)
      2. guest_name_cn wrapped as "Guest (汉字)" — safe non-breaking fallback
      3. fallback string
    """
    if guest_name and guest_name.strip():
        return guest_name.strip()
    if guest_name_cn and guest_name_cn.strip():
        cn = guest_name_cn.strip()
        # If the "Chinese" name is actually ASCII, use it directly
        if all(ord(c) < 128 for c in cn):
            return cn
        return f"Guest ({cn})"
    return fallback


def default_cny_currency(currency: Optional[str]) -> str:
    """Return CNY if the currency field is absent or empty."""
    if currency and currency.strip():
        return currency.strip().upper()
    return "CNY"


class TripComAdapter(OTAAdapter):
    """
    Trip.com / Ctrip OTA adapter — China market Tier 2.

    Phase 238 enhanced: Ctrip-specific field handling, Chinese guest names,
    CNY-first currency, cancellation codes.

    Follows standard adapter interface (Phase 35+).
    booking_id = "tripcom_{normalized_booking_ref}"
    property field: hotel_id → property_id
    currency: primarily CNY, also THB/USD/JPY
    """

    provider = "tripcom"

    def normalize(self, payload: dict) -> NormalizedBookingEvent:
        """
        Normalize Trip.com / Ctrip webhook payload into canonical structure.

        Supports both legacy (order_id) and Ctrip (booking_ref) field names.
        CTRIP- and TC- prefixes are stripped by booking_identity module.

        Guest name resolution:
          - guest_name (ASCII) preferred
          - Falls back to guest_name_cn wrapped as "Guest (汉字)"

        Currency:
          - Defaults to CNY if absent

        Fields:
          event_id      → external_event_id
          booking_ref / order_id → reservation_id (prefix stripped)
          hotel_id      → property_id
          guest_name    → (romanized via romanize_guest_name)
          currency      → (CNY default via default_cny_currency)
        """
        enriched = normalize_schema(self.provider, payload)

        # Ctrip uses booking_ref; legacy Trip.com uses order_id
        raw_ref = payload.get("booking_ref") or payload.get("order_id", "")

        # Enrich payload with Ctrip-specific resolved fields
        enriched["_resolved_guest_name"] = romanize_guest_name(
            payload.get("guest_name"),
            payload.get("guest_name_cn"),
        )
        enriched["_resolved_currency"] = default_cny_currency(
            payload.get("currency"),
        )
        enriched["_cancellation_reason"] = resolve_ctrip_cancel_reason(
            payload.get("cancellation_code"),
        )

        return NormalizedBookingEvent(
            tenant_id=payload["tenant_id"],
            provider=self.provider,
            external_event_id=payload["event_id"],
            reservation_id=normalize_reservation_ref(self.provider, raw_ref),
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
        elif canonical_type == "BOOKING_CANCELED":
            canonical_payload = {
                "provider": self.provider,
                "reservation_id": normalized.reservation_id,
                "property_id": normalized.property_id,
                "cancellation_reason": normalized.payload.get(
                    "_cancellation_reason", "unknown"
                ),
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
