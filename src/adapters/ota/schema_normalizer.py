"""
schema_normalizer.py — Phase 77

Enriches a raw OTA provider payload with canonical field names.
Canonical keys added to the returned copy:
  - canonical_guest_count  (int | None)
  - canonical_booking_ref  (str | None)
  - canonical_property_id  (str | None)

Rules:
- Returns a shallow copy of the payload — original keys are never removed.
- Missing fields → None (never raises KeyError).
- Supports all 5 providers: bookingcom, airbnb, expedia, agoda, tripcom.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Provider-specific extraction helpers
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
        return None
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_schema(provider: str, payload: dict) -> dict:
    """
    Return a shallow copy of *payload* enriched with canonical field names.

    New keys always added:
      canonical_guest_count  — int or None
      canonical_booking_ref  — str or None
      canonical_property_id  — str or None

    Existing keys are never removed or renamed.
    Supports providers: bookingcom, airbnb, expedia, agoda, tripcom.
    Unknown providers are passed through with all canonical keys set to None.
    """
    enriched: dict[str, Any] = dict(payload)
    enriched["canonical_guest_count"] = _guest_count(provider, payload)
    enriched["canonical_booking_ref"] = _booking_ref(provider, payload)
    enriched["canonical_property_id"] = _property_id(provider, payload)
    return enriched
