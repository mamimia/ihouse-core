"""
schema_normalizer.py — Phase 77 + Phase 78 + Phase 83 + Phase 85

Enriches a raw OTA provider payload with canonical field names.

Canonical keys added to the returned copy (all are additive — originals never removed):

  Phase 77:
    canonical_guest_count  (int | None)
    canonical_booking_ref  (str | None)
    canonical_property_id  (str | None)

  Phase 78:
    canonical_check_in     (str | None)  — raw string from provider, no parsing
    canonical_check_out    (str | None)  — raw string from provider, no parsing
    canonical_currency     (str | None)  — ISO 4217 code
    canonical_total_price  (str | None)  — raw string value, no Decimal conversion

Rules:
- Returns a shallow copy of the payload — original keys are never removed.
- Missing or unparseable fields -> None (never raises KeyError).
- Supports all 8 providers: bookingcom, airbnb, expedia, agoda, tripcom, vrbo, gvr, traveloka.
- Unknown providers pass through with all canonical keys set to None.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Phase 77 extraction helpers
# ---------------------------------------------------------------------------

def _guest_count(provider: str, payload: dict) -> int | None:
    """Extract guest count from provider-specific field."""
    try:
        if provider == "bookingcom":
            return int(payload["number_of_guests"])
        elif provider == "airbnb":
            return int(payload["guest_count"])
        elif provider == "expedia":
            # Expedia nests it: guests: {count: N}
            return int(payload["guests"]["count"])
        elif provider == "agoda":
            return int(payload["num_guests"])
        elif provider == "tripcom":
            return int(payload["guests"])
        elif provider == "vrbo":
            return int(payload["guest_count"])
        elif provider == "gvr":
            return int(payload["guest_count"])
        elif provider == "traveloka":
            return int(payload["num_guests"])
        return None
    except (KeyError, TypeError, ValueError):
        return None


def _booking_ref(provider: str, payload: dict) -> str | None:
    """Extract the provider-native booking reference."""
    try:
        if provider == "bookingcom":
            return str(payload["reservation_id"])
        elif provider == "airbnb":
            return str(payload["reservation_id"])
        elif provider == "expedia":
            return str(payload["reservation_id"])
        elif provider == "agoda":
            return str(payload["booking_ref"])
        elif provider == "tripcom":
            return str(payload["order_id"])
        elif provider == "vrbo":
            return str(payload["reservation_id"])
        elif provider == "gvr":
            # GVR uses gvr_booking_id as its native booking reference
            return str(payload["gvr_booking_id"])
        elif provider == "traveloka":
            # Traveloka uses booking_code (may include TV- prefix)
            return str(payload["booking_code"])
        return None
    except (KeyError, TypeError):
        return None


def _property_id(provider: str, payload: dict) -> str | None:
    """Extract the property identifier from provider-specific field."""
    try:
        if provider == "bookingcom":
            return str(payload["property_id"])
        elif provider == "airbnb":
            return str(payload["listing_id"])
        elif provider == "expedia":
            return str(payload["property_id"])
        elif provider == "agoda":
            return str(payload["property_id"])
        elif provider == "tripcom":
            return str(payload["hotel_id"])
        elif provider == "vrbo":
            return str(payload["unit_id"])  # Vrbo uses unit_id
        elif provider == "gvr":
            return str(payload["property_id"])  # GVR uses standard property_id
        elif provider == "traveloka":
            return str(payload["property_code"])  # Traveloka uses property_code
        return None
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Phase 78 extraction helpers
# ---------------------------------------------------------------------------

def _check_in(provider: str, payload: dict) -> str | None:
    """Extract check-in date as raw string from provider-specific field.

    Field mapping:
      bookingcom -> check_in
      airbnb     -> check_in
      expedia    -> check_in_date
      agoda      -> check_in
      tripcom    -> arrival_date
      vrbo       -> arrival_date
    """
    try:
        if provider == "bookingcom":
            return str(payload["check_in"])
        elif provider == "airbnb":
            return str(payload["check_in"])
        elif provider == "expedia":
            return str(payload["check_in_date"])
        elif provider == "agoda":
            return str(payload["check_in"])
        elif provider == "tripcom":
            return str(payload["arrival_date"])
        elif provider == "vrbo":
            return str(payload["arrival_date"])
        elif provider == "gvr":
            return str(payload["check_in"])
        elif provider == "traveloka":
            return str(payload["check_in_date"])  # Traveloka: check_in_date
        return None
    except (KeyError, TypeError):
        return None


def _check_out(provider: str, payload: dict) -> str | None:
    """Extract check-out date as raw string from provider-specific field.

    Field mapping:
      bookingcom -> check_out
      airbnb     -> check_out
      expedia    -> check_out_date
      agoda      -> check_out
      tripcom    -> departure_date
      vrbo       -> departure_date
    """
    try:
        if provider == "bookingcom":
            return str(payload["check_out"])
        elif provider == "airbnb":
            return str(payload["check_out"])
        elif provider == "expedia":
            return str(payload["check_out_date"])
        elif provider == "agoda":
            return str(payload["check_out"])
        elif provider == "tripcom":
            return str(payload["departure_date"])
        elif provider == "vrbo":
            return str(payload["departure_date"])
        elif provider == "gvr":
            return str(payload["check_out"])
        elif provider == "traveloka":
            return str(payload["check_out_date"])  # Traveloka: check_out_date
        return None
    except (KeyError, TypeError):
        return None


def _currency(provider: str, payload: dict) -> str | None:
    """Extract ISO 4217 currency code.

    Most providers use 'currency'. Traveloka uses 'currency_code'.
    """
    try:
        if provider == "traveloka":
            val = payload.get("currency_code")
        else:
            val = payload.get("currency")
        return str(val) if val is not None else None
    except (KeyError, TypeError):
        return None


def _total_price(provider: str, payload: dict) -> str | None:
    """Extract gross booking amount as raw string.

    Field mapping:
      bookingcom -> total_price
      airbnb     -> booking_subtotal
      expedia    -> total_amount
      agoda      -> selling_rate
      tripcom    -> order_amount
      vrbo       -> traveler_payment

    Returns raw str value. No Decimal conversion — financial_extractor owns precision.
    """
    try:
        if provider == "bookingcom":
            val = payload["total_price"]
        elif provider == "airbnb":
            val = payload["booking_subtotal"]
        elif provider == "expedia":
            val = payload["total_amount"]
        elif provider == "agoda":
            val = payload["selling_rate"]
        elif provider == "tripcom":
            val = payload["order_amount"]
        elif provider == "vrbo":
            val = payload["traveler_payment"]
        elif provider == "gvr":
            val = payload["booking_value"]
        elif provider == "traveloka":
            val = payload["booking_total"]  # Traveloka: booking_total
        else:
            return None
        return str(val) if val is not None else None
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_schema(provider: str, payload: dict) -> dict:
    """Return a shallow copy of *payload* enriched with canonical field names.

    New keys always added (Phase 77):
      canonical_guest_count  -- int or None
      canonical_booking_ref  -- str or None
      canonical_property_id  -- str or None

    New keys always added (Phase 78):
      canonical_check_in     -- str or None (raw provider value)
      canonical_check_out    -- str or None (raw provider value)
      canonical_currency     -- str or None (ISO 4217)
      canonical_total_price  -- str or None (raw provider value)

    Existing keys are never removed or renamed.
    Supports providers: bookingcom, airbnb, expedia, agoda, tripcom, vrbo, gvr.
    Unknown providers are passed through with all canonical keys set to None.
    """
    enriched: dict[str, Any] = dict(payload)
    # Phase 77
    enriched["canonical_guest_count"] = _guest_count(provider, payload)
    enriched["canonical_booking_ref"] = _booking_ref(provider, payload)
    enriched["canonical_property_id"] = _property_id(provider, payload)
    # Phase 78
    enriched["canonical_check_in"] = _check_in(provider, payload)
    enriched["canonical_check_out"] = _check_out(provider, payload)
    enriched["canonical_currency"] = _currency(provider, payload)
    enriched["canonical_total_price"] = _total_price(provider, payload)
    return enriched
