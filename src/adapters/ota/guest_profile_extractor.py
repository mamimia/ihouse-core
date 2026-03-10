"""
Phase 159 — Guest Profile Extractor

Extracts canonical guest fields (name, email, phone) from OTA webhook payloads.
Each OTA provider uses different field names — this module normalises them all.

PII rules:
  - Extracted fields are stored in `guest_profile` table only.
  - They must NEVER be written to event_log or booking_state.
  - Extraction is best-effort — missing fields → None, never raises.

Supported providers:
  airbnb, bookingcom, expedia, vrbo, hotelbeds, agoda, tripadvisor,
  klook, booking_identity, despegar, traveloka, tripcom, gvr, makemytrip (defaults)
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Canonical result type
# ---------------------------------------------------------------------------

class GuestProfile:
    """Extracted guest fields from an OTA payload."""

    __slots__ = ("guest_name", "guest_email", "guest_phone", "source")

    def __init__(
        self,
        guest_name:  Optional[str] = None,
        guest_email: Optional[str] = None,
        guest_phone: Optional[str] = None,
        source:      Optional[str] = None,
    ) -> None:
        self.guest_name  = _clean(guest_name)
        self.guest_email = _clean(guest_email)
        self.guest_phone = _clean(guest_phone)
        self.source      = _clean(source)

    def is_empty(self) -> bool:
        """True if no meaningful data was extracted."""
        return not any([self.guest_name, self.guest_email, self.guest_phone])

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "guest_name":  self.guest_name,
            "guest_email": self.guest_email,
            "guest_phone": self.guest_phone,
            "source":      self.source,
        }

    def __repr__(self) -> str:
        return (
            f"GuestProfile(name={self.guest_name!r}, "
            f"email={self.guest_email!r}, phone={self.guest_phone!r})"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean(value: Any) -> Optional[str]:
    """Strip whitespace; return None for blank/None values."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _first(*values: Any) -> Optional[str]:
    """Return the first non-blank value from a sequence of candidates."""
    for v in values:
        cleaned = _clean(v)
        if cleaned is not None:
            return cleaned
    return None


# ---------------------------------------------------------------------------
# Provider-specific extractors
# ---------------------------------------------------------------------------

def _extract_airbnb(payload: Dict[str, Any]) -> GuestProfile:
    guest = payload.get("guest") or {}
    if isinstance(guest, str):
        # Some Airbnb test payloads put the name directly as a string
        return GuestProfile(
            guest_name=guest,
            guest_email=payload.get("guest_email"),
            guest_phone=payload.get("guest_phone"),
            source="airbnb",
        )
    return GuestProfile(
        guest_name=_first(
            guest.get("name"),
            guest.get("display_name"),
            payload.get("guest_name"),
        ),
        guest_email=_first(guest.get("email"), payload.get("guest_email")),
        guest_phone=_first(guest.get("phone"), payload.get("guest_phone")),
        source="airbnb",
    )


def _extract_bookingcom(payload: Dict[str, Any]) -> GuestProfile:
    booker = payload.get("booker") or {}
    return GuestProfile(
        guest_name=_first(
            booker.get("first_name") and booker.get("last_name") and
            f"{booker['first_name']} {booker['last_name']}".strip(),
            booker.get("name"),
            payload.get("guest_name"),
        ),
        guest_email=_first(booker.get("email"), payload.get("guest_email")),
        guest_phone=_first(booker.get("phone"), booker.get("telephone"), payload.get("guest_phone")),
        source="bookingcom",
    )


def _extract_expedia(payload: Dict[str, Any]) -> GuestProfile:
    primary = payload.get("primaryGuest") or payload.get("primary_guest") or {}
    return GuestProfile(
        guest_name=_first(
            primary.get("givenName") and primary.get("surName") and
            f"{primary['givenName']} {primary['surName']}".strip(),
            primary.get("name"),
            payload.get("guest_name"),
        ),
        guest_email=_first(primary.get("email"), payload.get("guest_email")),
        guest_phone=_first(primary.get("phone"), payload.get("guest_phone")),
        source="expedia",
    )


def _extract_vrbo(payload: Dict[str, Any]) -> GuestProfile:
    # VRBO often nests under "renter" or "reservationGuest"
    renter = payload.get("renter") or payload.get("reservationGuest") or {}
    return GuestProfile(
        guest_name=_first(
            renter.get("firstName") and renter.get("lastName") and
            f"{renter['firstName']} {renter['lastName']}".strip(),
            renter.get("name"),
            payload.get("guest_name"),
        ),
        guest_email=_first(renter.get("email"), payload.get("guest_email")),
        guest_phone=_first(renter.get("phone"), renter.get("phoneNumber"), payload.get("guest_phone")),
        source="vrbo",
    )


def _extract_generic(provider: str, payload: Dict[str, Any]) -> GuestProfile:
    """Generic extractor covering all other providers using common field names."""
    # Try nested "guest" object first
    guest_obj = payload.get("guest") or {}
    if not isinstance(guest_obj, dict):
        guest_obj = {}

    first  = _first(guest_obj.get("first_name"), guest_obj.get("firstName"))
    last   = _first(guest_obj.get("last_name"),  guest_obj.get("lastName"))
    composed = f"{first} {last}".strip() if (first and last) else None

    return GuestProfile(
        guest_name=_first(
            composed,
            guest_obj.get("name"),
            payload.get("guest_name"),
            payload.get("booker_name"),
            payload.get("traveler_name"),
        ),
        guest_email=_first(
            guest_obj.get("email"),
            payload.get("guest_email"),
            payload.get("booker_email"),
        ),
        guest_phone=_first(
            guest_obj.get("phone"),
            guest_obj.get("phone_number"),
            payload.get("guest_phone"),
            payload.get("booker_phone"),
        ),
        source=provider,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_EXTRACTOR_MAP = {
    "airbnb":     _extract_airbnb,
    "bookingcom": _extract_bookingcom,
    "expedia":    _extract_expedia,
    "vrbo":       _extract_vrbo,
}


def extract_guest_profile(provider: str, payload: Dict[str, Any]) -> GuestProfile:
    """
    Extract a normalised GuestProfile from an OTA webhook payload.

    Never raises — returns an empty GuestProfile on any error.

    Args:
        provider: OTA provider name (e.g. "airbnb", "bookingcom")
        payload:  Raw incoming webhook payload dict

    Returns:
        GuestProfile with extracted fields (any may be None)
    """
    try:
        extractor = _EXTRACTOR_MAP.get(provider)
        if extractor is not None:
            return extractor(payload)
        return _extract_generic(provider, payload)
    except Exception:
        return GuestProfile(source=provider)
