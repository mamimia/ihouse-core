"""
Phase 65 — Financial Data Foundation

BookingFinancialFacts: immutable, validated financial field container.
extract_financial_facts(): public API — delegates to per-provider extractor.

Rules:
- All monetary fields use Decimal for precision (no float).
- All fields are Optional — absent provider fields become None, no exception.
- source_confidence is FULL when all key financial fields are present,
  PARTIAL when some are missing, ESTIMATED when a value is derived.
- raw_financial_fields preserves verbatim provider values for audit.
- This module has zero side effects. Pure extraction functions only.
- No DB writes. No booking_state mutation. No canonical envelope changes.

Invariant (locked Phase 62+):
  booking_state must NEVER contain financial calculations.
  financial_facts exist on NormalizedBookingEvent only, for future use.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

CONFIDENCE_FULL = "FULL"        # All key financial fields present
CONFIDENCE_PARTIAL = "PARTIAL"  # Some key fields missing
CONFIDENCE_ESTIMATED = "ESTIMATED"  # A value was derived, not directly provided


# ---------------------------------------------------------------------------
# BookingFinancialFacts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BookingFinancialFacts:
    """
    Immutable, validated financial field container.

    Represents the financial picture of one booking as reported by its
    OTA provider. Fields are provider-specific — not all providers expose
    the same financial data.

    Produced by extract_financial_facts() during OTA adapter normalization.
    Never written to booking_state (invariant — Phase 62+).
    """

    provider: str
    total_price: Optional[Decimal]          # Gross booking amount
    currency: Optional[str]                 # ISO 4217 (e.g. "USD", "EUR")
    ota_commission: Optional[Decimal]       # OTA commission amount or rate
    taxes: Optional[Decimal]               # Tax amount (if provided)
    fees: Optional[Decimal]                # Platform / channel fees
    net_to_property: Optional[Decimal]     # Net payout to property owner
    source_confidence: str                 # FULL | PARTIAL | ESTIMATED
    raw_financial_fields: Dict[str, Any]   # Verbatim provider values (audit)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_decimal(value: Any) -> Optional[Decimal]:
    """
    Safely convert a value to Decimal.
    Returns None if value is None or cannot be converted.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _confidence(required_present: list[bool]) -> str:
    """
    Determine confidence from a list of booleans indicating whether each
    key financial field is present.
    """
    if all(required_present):
        return CONFIDENCE_FULL
    return CONFIDENCE_PARTIAL


# ---------------------------------------------------------------------------
# Per-provider extractors
# ---------------------------------------------------------------------------

def _extract_bookingcom(payload: dict) -> BookingFinancialFacts:
    """
    Booking.com financial fields:
      total_price      — gross booking amount
      currency         — ISO 4217 currency code
      commission       — OTA commission amount (not %)
      net              — net payout to property
    Confidence: FULL if all 4 present, PARTIAL if any missing.
    """
    total_price = _to_decimal(payload.get("total_price"))
    currency = payload.get("currency")
    commission = _to_decimal(payload.get("commission"))
    net = _to_decimal(payload.get("net"))

    raw: Dict[str, Any] = {}
    for k in ("total_price", "currency", "commission", "net"):
        if k in payload:
            raw[k] = payload[k]

    confidence = _confidence([
        total_price is not None,
        currency is not None,
        commission is not None,
        net is not None,
    ])

    return BookingFinancialFacts(
        provider="bookingcom",
        total_price=total_price,
        currency=currency,
        ota_commission=commission,
        taxes=None,          # Booking.com does not expose taxes in webhook
        fees=None,           # Not exposed separately
        net_to_property=net,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )


def _extract_expedia(payload: dict) -> BookingFinancialFacts:
    """
    Expedia financial fields:
      total_amount       — gross booking amount
      currency           — ISO 4217 currency code
      commission_percent — OTA commission as a percentage (not absolute amount)
    Confidence: PARTIAL (no native net field; commission is %, not amount).
    """
    total_amount = _to_decimal(payload.get("total_amount"))
    currency = payload.get("currency")
    commission_pct = _to_decimal(payload.get("commission_percent"))

    raw: Dict[str, Any] = {}
    for k in ("total_amount", "currency", "commission_percent"):
        if k in payload:
            raw[k] = payload[k]

    # commission_percent needs total_amount to derive net — mark ESTIMATED if derivable
    if total_amount is not None and commission_pct is not None:
        derived_commission = (total_amount * commission_pct / Decimal("100")).quantize(
            Decimal("0.01")
        )
        derived_net = (total_amount - derived_commission).quantize(Decimal("0.01"))
        confidence = CONFIDENCE_ESTIMATED
    else:
        derived_commission = None
        derived_net = None
        confidence = CONFIDENCE_PARTIAL

    return BookingFinancialFacts(
        provider="expedia",
        total_price=total_amount,
        currency=currency,
        ota_commission=derived_commission,
        taxes=None,
        fees=None,
        net_to_property=derived_net,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )


def _extract_airbnb(payload: dict) -> BookingFinancialFacts:
    """
    Airbnb financial fields:
      payout_amount    — net payout to host (= net_to_property)
      booking_subtotal — gross booking subtotal (before Airbnb fees)
      taxes            — tax amount included in booking
    Confidence: PARTIAL (no OTA commission exposed directly; Airbnb absorbs
    service fee on guest side).
    """
    payout = _to_decimal(payload.get("payout_amount"))
    subtotal = _to_decimal(payload.get("booking_subtotal"))
    taxes = _to_decimal(payload.get("taxes"))
    currency = payload.get("currency")

    raw: Dict[str, Any] = {}
    for k in ("payout_amount", "booking_subtotal", "taxes", "currency"):
        if k in payload:
            raw[k] = payload[k]

    confidence = _confidence([
        payout is not None,
        subtotal is not None,
    ])

    return BookingFinancialFacts(
        provider="airbnb",
        total_price=subtotal,
        currency=currency,
        ota_commission=None,       # Airbnb does not expose commission directly
        taxes=taxes,
        fees=None,
        net_to_property=payout,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )


def _extract_agoda(payload: dict) -> BookingFinancialFacts:
    """
    Agoda financial fields:
      selling_rate — gross rate charged to guest (= total_price)
      net_rate     — net payout to property (= net_to_property)
      currency     — ISO 4217 currency code
    Confidence: FULL if both selling_rate and net_rate present, PARTIAL otherwise.
    """
    selling_rate = _to_decimal(payload.get("selling_rate"))
    net_rate = _to_decimal(payload.get("net_rate"))
    currency = payload.get("currency")

    raw: Dict[str, Any] = {}
    for k in ("selling_rate", "net_rate", "currency"):
        if k in payload:
            raw[k] = payload[k]

    # Derive implied commission if both rates available
    if selling_rate is not None and net_rate is not None:
        implied_commission = (selling_rate - net_rate).quantize(Decimal("0.01"))
    else:
        implied_commission = None

    confidence = _confidence([
        selling_rate is not None,
        net_rate is not None,
        currency is not None,
    ])

    return BookingFinancialFacts(
        provider="agoda",
        total_price=selling_rate,
        currency=currency,
        ota_commission=implied_commission,
        taxes=None,
        fees=None,
        net_to_property=net_rate,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )


def _extract_tripcom(payload: dict) -> BookingFinancialFacts:
    """
    Trip.com financial fields:
      order_amount — gross booking amount
      channel_fee  — channel / platform fee (not a % commission)
      currency     — ISO 4217 currency code
    Confidence: PARTIAL (no net field directly; channel_fee is absolute, not %).
    """
    order_amount = _to_decimal(payload.get("order_amount"))
    channel_fee = _to_decimal(payload.get("channel_fee"))
    currency = payload.get("currency")

    raw: Dict[str, Any] = {}
    for k in ("order_amount", "channel_fee", "currency"):
        if k in payload:
            raw[k] = payload[k]

    # Derive net if both present
    if order_amount is not None and channel_fee is not None:
        derived_net = (order_amount - channel_fee).quantize(Decimal("0.01"))
        confidence = CONFIDENCE_ESTIMATED
    else:
        derived_net = None
        confidence = CONFIDENCE_PARTIAL

    return BookingFinancialFacts(
        provider="tripcom",
        total_price=order_amount,
        currency=currency,
        ota_commission=channel_fee,
        taxes=None,
        fees=channel_fee,          # channel_fee serves as the fee field too
        net_to_property=derived_net,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )

def _extract_vrbo(payload: dict) -> BookingFinancialFacts:
    """
    Vrbo financial fields:
      traveler_payment — gross amount charged to guest (= total_price)
      manager_payment  — net payout to property manager (= net_to_property)
      service_fee      — Vrbo platform service fee
      currency         — ISO 4217 currency code
    Confidence: FULL if traveler_payment + manager_payment + currency present,
                PARTIAL otherwise.
    """
    traveler_payment = _to_decimal(payload.get("traveler_payment"))
    manager_payment = _to_decimal(payload.get("manager_payment"))
    service_fee = _to_decimal(payload.get("service_fee"))
    currency = payload.get("currency")

    raw: Dict[str, Any] = {}
    for k in ("traveler_payment", "manager_payment", "service_fee", "currency"):
        if k in payload:
            raw[k] = payload[k]

    # Derive implied commission from service_fee if available
    implied_commission = service_fee  # service_fee is the Vrbo platform cut

    confidence = _confidence([
        traveler_payment is not None,
        manager_payment is not None,
        currency is not None,
    ])

    return BookingFinancialFacts(
        provider="vrbo",
        total_price=traveler_payment,
        currency=currency,
        ota_commission=implied_commission,
        taxes=None,           # Vrbo does not expose taxes separately
        fees=service_fee,
        net_to_property=manager_payment,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )



def _extract_gvr(payload: dict) -> BookingFinancialFacts:
    """
    Google Vacation Rentals financial fields:
      booking_value — gross booking amount as reported by GVR
      net_amount    — net payout to property (may be absent, derived from booking_value - google_fee)
      google_fee    — Google's platform fee (if applicable)
      currency      — ISO 4217 currency code

    Note: GVR financial data may originate from a connected OTA channel.
    When google_fee is absent, ota_commission is None.
    When net_amount is absent but booking_value + google_fee are present, net is derived.
    Confidence: FULL if booking_value + currency present, PARTIAL otherwise.
    """
    booking_value = _to_decimal(payload.get("booking_value"))
    net_amount = _to_decimal(payload.get("net_amount"))
    google_fee = _to_decimal(payload.get("google_fee"))
    currency = payload.get("currency")

    raw: Dict[str, Any] = {}
    for k in ("booking_value", "net_amount", "google_fee", "currency"):
        if k in payload:
            raw[k] = payload[k]

    # Derive net if missing but booking_value + google_fee are present
    if net_amount is None and booking_value is not None and google_fee is not None:
        net_amount = (booking_value - google_fee).quantize(Decimal("0.01"))
        confidence = CONFIDENCE_ESTIMATED
    else:
        confidence = _confidence([
            booking_value is not None,
            currency is not None,
        ])

    return BookingFinancialFacts(
        provider="gvr",
        total_price=booking_value,
        currency=currency,
        ota_commission=google_fee,    # google_fee is Google's cut
        taxes=None,                   # GVR does not expose taxes separately
        fees=google_fee,
        net_to_property=net_amount,
        source_confidence=confidence,
        raw_financial_fields=raw,
    )


_EXTRACTORS = {
    "bookingcom": _extract_bookingcom,
    "expedia": _extract_expedia,
    "airbnb": _extract_airbnb,
    "agoda": _extract_agoda,
    "tripcom": _extract_tripcom,
    "vrbo": _extract_vrbo,
    "gvr": _extract_gvr,
}

# ---------------------------------------------------------------------------
# Traveloka extractor (Phase 88)
# ---------------------------------------------------------------------------

def _extract_traveloka(payload: dict) -> BookingFinancialFacts:
    """
    Traveloka financial fields:
      booking_total  — gross booking amount charged to guest (= total_price)
      traveloka_fee  — Traveloka platform commission (= ota_commission, optional)
      net_payout     — net payout to property after commission (optional)
      currency_code  — ISO 4217 currency code (note: 'currency_code' not 'currency')

    When net_payout is absent but booking_total + traveloka_fee are present,
    net is derived: net = booking_total - traveloka_fee → confidence = ESTIMATED.

    Confidence: FULL if booking_total + currency_code + net_payout present,
                ESTIMATED if net_payout derived,
                PARTIAL if booking_total or currency_code missing.
    """
    booking_total = _to_decimal(payload.get("booking_total"))
    traveloka_fee = _to_decimal(payload.get("traveloka_fee"))
    net_payout_raw = payload.get("net_payout")
    net_payout = _to_decimal(net_payout_raw)
    currency = payload.get("currency_code")

    raw: Dict[str, Any] = {}
    for k in ("booking_total", "traveloka_fee", "net_payout", "currency_code"):
        if k in payload:
            raw[k] = payload[k]

    source_confidence: str
    derived_net = net_payout

    if net_payout is None and booking_total is not None and traveloka_fee is not None:
        derived_net = booking_total - traveloka_fee
        source_confidence = "ESTIMATED"
    elif booking_total is None or currency is None:
        source_confidence = "PARTIAL"
    else:
        source_confidence = "FULL"

    return BookingFinancialFacts(
        provider="traveloka",
        total_price=booking_total,
        currency=currency,
        ota_commission=traveloka_fee,
        taxes=None,           # Traveloka does not expose taxes separately
        fees=traveloka_fee,
        net_to_property=derived_net,
        source_confidence=source_confidence,
        raw_financial_fields=raw,
    )


_EXTRACTORS["traveloka"] = _extract_traveloka


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_financial_facts(provider: str, payload: dict) -> BookingFinancialFacts:
    """
    Extract structured financial facts from a raw OTA provider payload.

    Args:
        provider: OTA provider identifier (e.g. "bookingcom", "expedia").
        payload:  Raw webhook payload dict from the provider.

    Returns:
        BookingFinancialFacts — immutable, validated. All fields are Optional;
        missing provider data becomes None. Never raises on absent fields.

    Raises:
        ValueError: If provider is not registered (programming error, not a
                    runtime data error).
    """
    extractor = _EXTRACTORS.get(provider)
    if extractor is None:
        raise ValueError(
            f"No financial extractor registered for provider '{provider}'. "
            f"Registered providers: {sorted(_EXTRACTORS)}"
        )
    return extractor(payload)
