from __future__ import annotations

from typing import Any, Dict, Optional

from .date_normalizer import normalize_date
from .schemas import AmendmentFields


# ---------------------------------------------------------------------------
# Known providers
# ---------------------------------------------------------------------------

_SUPPORTED_PROVIDERS = {"bookingcom", "expedia", "airbnb", "agoda", "tripcom", "vrbo", "gvr", "traveloka", "makemytrip", "klook"}


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
        new_check_in=normalize_date(_nonempty(info.get("arrival_date"))),
        new_check_out=normalize_date(_nonempty(info.get("departure_date"))),
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
        new_check_in=normalize_date(_nonempty(dates.get("check_in"))),
        new_check_out=normalize_date(_nonempty(dates.get("check_out"))),
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
        new_check_in=normalize_date(_nonempty(alteration.get("new_check_in"))),
        new_check_out=normalize_date(_nonempty(alteration.get("new_check_out"))),
        new_guest_count=_int_or_none(alteration.get("guest_count")),
        amendment_reason=_nonempty(alteration.get("reason")),
    )


def extract_amendment_agoda(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from an Agoda webhook payload.

    Agoda sends amendment data under 'modification':

        {
          "modification": {
            "check_in_date":  "2026-09-01",
            "check_out_date": "2026-09-05",
            "num_guests":     2,
            "reason":         "date_change"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    modification = provider_payload.get("modification") or {}

    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(modification.get("check_in_date"))),
        new_check_out=normalize_date(_nonempty(modification.get("check_out_date"))),
        new_guest_count=_int_or_none(modification.get("num_guests")),
        amendment_reason=_nonempty(modification.get("reason")),
    )


def extract_amendment_tripcom(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a Trip.com webhook payload.

    Trip.com sends amendment data under 'changes':

        {
          "changes": {
            "check_in":  "2026-09-01",
            "check_out": "2026-09-05",
            "guests":    2,
            "remark":    "date_adjustment"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    changes = provider_payload.get("changes") or {}

    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(changes.get("check_in"))),
        new_check_out=normalize_date(_nonempty(changes.get("check_out"))),
        new_guest_count=_int_or_none(changes.get("guests")),
        amendment_reason=_nonempty(changes.get("remark")),
    )


def extract_amendment_vrbo(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a Vrbo webhook payload.

    Vrbo sends amendment data under 'alteration':

        {
          "alteration": {
            "new_check_in":     "2026-12-01",
            "new_check_out":    "2026-12-08",
            "new_guest_count": 3,
            "amendment_reason": "guest_request"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    alteration = provider_payload.get("alteration") or {}

    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(alteration.get("new_check_in"))),
        new_check_out=normalize_date(_nonempty(alteration.get("new_check_out"))),
        new_guest_count=_int_or_none(alteration.get("new_guest_count")),
        amendment_reason=_nonempty(alteration.get("amendment_reason")),
    )


def extract_amendment_gvr(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a GVR webhook payload.

    GVR sends amendment data under 'modification':

        {
          "modification": {
            "check_in":        "2026-12-01",
            "check_out":       "2026-12-08",
            "guest_count":     3,
            "reason":          "guest_request"
          }
        }

    Returns AmendmentFields with None for any missing field.
    """
    modification = provider_payload.get("modification") or {}

    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(modification.get("check_in"))),
        new_check_out=normalize_date(_nonempty(modification.get("check_out"))),
        new_guest_count=_int_or_none(modification.get("guest_count")),
        amendment_reason=_nonempty(modification.get("reason")),
    )


def extract_amendment_traveloka(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a Traveloka BOOKING_MODIFIED payload.

    Traveloka sends modification data under 'modification':
      modification.check_in_date        — new check-in date
      modification.check_out_date       — new check-out date
      modification.num_guests           — new guest count
      modification.modification_reason  — reason for modification
    """
    mod = provider_payload.get("modification") or {}
    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(mod.get("check_in_date"))),
        new_check_out=normalize_date(_nonempty(mod.get("check_out_date"))),
        new_guest_count=_int_or_none(mod.get("num_guests")),
        amendment_reason=_nonempty(mod.get("modification_reason")),
    )


def extract_amendment_makemytrip(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a MakeMyTrip BOOKING_MODIFIED payload.

    MakeMyTrip sends modification data under 'amendment':
      amendment.check_in   — new check-in date
      amendment.check_out  — new check-out date
      amendment.guests     — new guest count
      amendment.reason     — reason for modification
    """
    amend = provider_payload.get("amendment") or {}
    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(amend.get("check_in"))),
        new_check_out=normalize_date(_nonempty(amend.get("check_out"))),
        new_guest_count=_int_or_none(amend.get("guests")),
        amendment_reason=_nonempty(amend.get("reason")),
    )


def extract_amendment_klook(provider_payload: Dict[str, Any]) -> AmendmentFields:
    """
    Extract normalized amendment fields from a Klook BOOKING_MODIFIED payload.

    Klook sends modification data under 'modification':
      modification.travel_date   — new activity start date
      modification.end_date      — new activity end date
      modification.participants  — new participant count
      modification.reason        — reason for modification
    """
    mod = provider_payload.get("modification") or {}
    return AmendmentFields(
        new_check_in=normalize_date(_nonempty(mod.get("travel_date"))),
        new_check_out=normalize_date(_nonempty(mod.get("end_date"))),
        new_guest_count=_int_or_none(mod.get("participants")),
        amendment_reason=_nonempty(mod.get("reason")),
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
    elif normalized_provider == "agoda":
        return extract_amendment_agoda(payload)
    elif normalized_provider == "tripcom":
        return extract_amendment_tripcom(payload)
    elif normalized_provider == "vrbo":
        return extract_amendment_vrbo(payload)
    elif normalized_provider == "gvr":
        return extract_amendment_gvr(payload)
    elif normalized_provider == "traveloka":
        return extract_amendment_traveloka(payload)
    elif normalized_provider == "makemytrip":
        return extract_amendment_makemytrip(payload)
    elif normalized_provider == "klook":
        return extract_amendment_klook(payload)
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
