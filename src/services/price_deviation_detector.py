"""
Phase 246 — Price Deviation Detector

Pure service module — detects when an incoming booking price deviates
significantly from the stored rate card for the same (property, room_type, season).

Deviation threshold: ±15% of the base_rate.

Usage:
    from services.price_deviation_detector import check_price_deviation, DeviationResult

Design:
    - Pure function, no side effects, no DB writes
    - Returns a structured DeviationResult dataclass
    - Season inference: caller may pass explicit season; if omitted, naive check for HIGH/LOW
      using a simple Thai tourism calendar heuristic (November–March = high, rest = low)
    - If no matching rate card exists → returns no_rate_card=True (not an alert)
    - If deviation > DEVIATION_THRESHOLD → returns alert=True

Invariants:
    - Does not read from booking_state
    - Does not write to any table
    - Does not call external services
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

# ±15% deviation threshold
DEVIATION_THRESHOLD = Decimal("0.15")

# High-season months (Thai tourism calendar heuristic)
_HIGH_SEASON_MONTHS = {11, 12, 1, 2, 3}


@dataclass(frozen=True)
class DeviationResult:
    """Structured result from check_price_deviation."""

    booking_id: str
    property_id: str
    room_type: Optional[str]
    season: str
    incoming_price: Decimal
    base_rate: Optional[Decimal]
    currency: str

    # Outcome flags
    no_rate_card: bool = False       # True when no matching rate card found
    alert: bool = False              # True when deviation > threshold
    deviation_pct: Optional[Decimal] = None   # e.g. Decimal("22.5") means +22.5%
    direction: Optional[str] = None  # "above" | "below"


def _infer_season(check_in_month: Optional[int]) -> str:
    """
    Naïve season inference from check-in month.
    Returns "high" or "low".
    """
    if check_in_month is None:
        return "low"
    return "high" if check_in_month in _HIGH_SEASON_MONTHS else "low"


def _deviation(incoming: Decimal, base: Decimal) -> Decimal:
    """(incoming - base) / base"""
    if base == Decimal("0"):
        return Decimal("0")
    return (incoming - base) / base


def check_price_deviation(
    *,
    booking_id: str,
    property_id: str,
    incoming_price: Decimal,
    currency: str,
    rate_cards: list[dict],
    room_type: Optional[str] = None,
    season: Optional[str] = None,
    check_in_month: Optional[int] = None,
) -> DeviationResult:
    """
    Check whether the incoming booking price deviates from the rate card.

    Args:
        booking_id:     ID of the incoming booking (for the result record)
        property_id:    Property the booking is for
        incoming_price: The booking's total_price (per night) from the OTA
        currency:       Currency of the incoming price
        rate_cards:     List of rate_card dicts from DB for this property
                        Each dict: {room_type, season, base_rate, currency}
        room_type:      Optional room type from the booking (may be None)
        season:         Optional explicit season override ("high" | "low" | ...)
        check_in_month: Optional check-in month (1-12) for season inference

    Returns:
        DeviationResult
    """
    effective_season = season or _infer_season(check_in_month)

    # Find matching rate card: exact match on (room_type, season, currency)
    # If room_type is None, look for any card matching (season, currency)
    matching: Optional[dict] = None
    for card in rate_cards:
        card_currency = (card.get("currency") or "THB").upper()
        card_season = (card.get("season") or "").lower()
        card_room = card.get("room_type")

        if card_currency != currency.upper():
            continue
        if card_season != effective_season.lower():
            continue
        if room_type is not None and card_room is not None:
            if card_room.lower() != room_type.lower():
                continue

        matching = card
        break

    if matching is None:
        return DeviationResult(
            booking_id=booking_id,
            property_id=property_id,
            room_type=room_type,
            season=effective_season,
            incoming_price=incoming_price,
            base_rate=None,
            currency=currency,
            no_rate_card=True,
        )

    base_rate = Decimal(str(matching["base_rate"]))
    dev = _deviation(incoming_price, base_rate)
    dev_pct = (dev * Decimal("100")).quantize(Decimal("0.1"))
    is_alert = abs(dev) > DEVIATION_THRESHOLD
    direction = "above" if dev > Decimal("0") else "below"

    return DeviationResult(
        booking_id=booking_id,
        property_id=property_id,
        room_type=room_type or matching.get("room_type"),
        season=effective_season,
        incoming_price=incoming_price,
        base_rate=base_rate,
        currency=currency,
        no_rate_card=False,
        alert=is_alert,
        deviation_pct=dev_pct,
        direction=direction if is_alert else None,
    )
