from __future__ import annotations

from typing import Any, Dict, Optional

from .schemas import AmendmentFields


# ---------------------------------------------------------------------------
# Known providers
# ---------------------------------------------------------------------------

_SUPPORTED_PROVIDERS = {"bookingcom", "expedia", "airbnb"}


# ---------------------------------------------------------------------------
# Provider-specific extractors
# ---------------------------------------------------------------------------

def extract_amendment_bookingcom(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a Booking.com webhook payload.

    Booking.com sends amendment data under 'new_reservation_info':

        {
          "new_reservation_info": {
            "arrival_date":   "2026-09-01",
            "departure_date": "2026-09-05",
            "number_of_guests": 2,
            "modification_reason": "guest request"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    info = provider_payload.get("new_reservation_info") or {}

    return AmendmentFields(
        new_check_in=_nonempty(info.get("arrival_date")),
        new_check_out=_nonempty(info.get("departure_date")),
        new_guest_count=_int_or_none(info.get("number_of_guests")),
        amendment_reason=_nonempty(info.get("modification_reason")),
    )


def extract_amendment_expedia(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from an Expedia webhook payload.

    Expedia sends amendment data under 'changes.dates' and 'changes.guests':

        {
          "changes": {
            "dates": {
              "check_in":  "2026-09-01",
              "check_out": "2026-09-05"
            },
            "guests": {"count": 2},
            "reason": "guest preference"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    changes = provider_payload.get("changes") or {}
    dates = changes.get("dates") or {}
    guests = changes.get("guests") or {}

    return AmendmentFields(
        new_check_in=_nonempty(dates.get("check_in")),
        new_check_out=_nonempty(dates.get("check_out")),
        new_guest_count=_int_or_none(guests.get("count")),
        amendment_reason=_nonempty(changes.get("reason")),
    )


def extract_amendment_airbnb(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from an Airbnb webhook payload.

    Airbnb sends amendment data under 'alteration':

        {
          "alteration": {
            "new_check_in":  "2026-09-01",
            "new_check_out": "2026-09-05",
            "guest_count":   2,
            "reason":        "guest_request"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    alteration = provider_payload.get("alteration") or {}

    return AmendmentFields(
        new_check_in=_nonempty(alteration.get("new_check_in")),
        new_check_out=_nonempty(alteration.get("new_check_out")),
        new_guest_count=_int_or_none(alteration.get("guest_count")),
        amendment_reason=_nonempty(alteration.get("reason")),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def normalize_amendment(provider: str, payload: Dict[str, Any]) -> AmendmentFields:
    """
    Dispatch to the correct provider extractor and return normalized AmendmentFields.

    Args:
        provider: OTA provider name (e.g. 'bookingcom', 'expedia')
        payload:  raw OTA webhook payload dict

    Returns:
        AmendmentFields — provider-agnostic amendment data

    Raises:
        ValueError if provider is unknown
    """
    normalized_provider = str(provider).strip().lower()

    if normalized_provider == "bookingcom":
        return extract_amendment_bookingcom(payload)
    elif normalized_provider == "expedia":
        return extract_amendment_expedia(payload)
    elif normalized_provider == "airbnb":
        return extract_amendment_airbnb(payload)
    else:
        raise ValueError(
            f"Unknown provider '{provider}' — cannot extract amendment fields. "
            f"Supported: {sorted(_SUPPORTED_PROVIDERS)}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _nonempty(value: Optional[Any]) -> Optional[str]:
    """Return str if non-empty, else None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _int_or_none(value: Optional[Any]) -> Optional[int]:
    """Return int if convertible, else None."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
