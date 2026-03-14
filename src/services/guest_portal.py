"""
Phase 262 + Phase 666 — Guest Self-Service Portal Service
==========================================================

Read-only guest-facing service layer.

Guests access their booking info via:
  - booking_ref (e.g. "AIR-12345")
  - guest_token (short-lived access token, mocked for CI)

No auth middleware needed — endpoints are public but token-gated.
Pure in-memory stubs for contract testing; production implementations
inject real Supabase lookups via the provided lookup_fn callables.

Phase 666: Enhanced data model with extras, chat, GPS, and house info.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Supporting types (Phase 666)
# ---------------------------------------------------------------------------

@dataclass
class ExtraItem:
    """An extra service available to the guest."""
    extra_id: str
    name: str
    description: str
    icon: str
    price: float
    currency: str = "THB"
    category: str = "other"


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------

@dataclass
class GuestBookingView:
    """What a guest can see about their booking.

    Phase 666 additions:
        extras_available  — list of extras enabled for this property
        chat_enabled      — whether guest↔manager chat is active
        property_latitude / property_longitude — GPS coordinates
        checkout_time     — from property config (display in portal)
        House info fields — AC, hot water, parking, pool, etc.
    """
    booking_ref: str
    property_name: str
    property_address: str
    check_in_date: str
    check_out_date: str
    check_in_time: str          # e.g. "15:00"
    check_out_time: str         # e.g. "11:00"
    status: str
    guest_name: str
    nights: int
    wifi_name: str | None = None
    wifi_password: str | None = None
    access_code: str | None = None
    house_rules: list[str] = field(default_factory=list)
    emergency_contact: str | None = None
    # --- Phase 666 fields ---
    extras_available: list[ExtraItem] = field(default_factory=list)
    chat_enabled: bool = False
    property_latitude: float | None = None
    property_longitude: float | None = None
    # House info
    ac_instructions: str | None = None
    hot_water_info: str | None = None
    stove_instructions: str | None = None
    parking_info: str | None = None
    pool_instructions: str | None = None
    laundry_info: str | None = None
    tv_info: str | None = None
    safe_code: str | None = None
    extra_notes: str | None = None
    door_code: str | None = None
    key_location: str | None = None
    breaker_location: str | None = None
    trash_instructions: str | None = None


@dataclass
class GuestPortalError:
    code: str      # "not_found" | "token_invalid" | "forbidden"
    message: str


# ---------------------------------------------------------------------------
# Token validation (stub — production would verify JWT / short-link token)
# ---------------------------------------------------------------------------

def validate_guest_token(booking_ref: str, guest_token: str) -> bool:
    """
    Returns True if the token is valid for this booking_ref.

    In production: verifies a signed token containing booking_ref.
    For contract testing: any non-empty token is accepted UNLESS it
    starts with "INVALID" (simulates bad tokens).
    """
    if not guest_token or guest_token.startswith("INVALID"):
        return False
    return True


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

def get_guest_booking(
    booking_ref: str,
    guest_token: str,
    lookup_fn: Any,              # callable: (booking_ref) → GuestBookingView | None
) -> GuestBookingView | GuestPortalError:
    """
    Returns GuestBookingView for valid token + known booking,
    or GuestPortalError for invalid token / unknown booking.
    """
    if not validate_guest_token(booking_ref, guest_token):
        return GuestPortalError(code="token_invalid", message="Access token is invalid or expired.")

    result = lookup_fn(booking_ref)
    if result is None:
        return GuestPortalError(code="not_found", message=f"Booking '{booking_ref}' not found.")

    return result


# ---------------------------------------------------------------------------
# Stub lookup (used by router for CI — no real DB)
# ---------------------------------------------------------------------------

_STUB_BOOKINGS: dict[str, GuestBookingView] = {
    "DEMO-001": GuestBookingView(
        booking_ref="DEMO-001",
        property_name="Villa Serenity",
        property_address="123 Sunset Road, Koh Samui, Thailand",
        check_in_date="2026-03-15",
        check_out_date="2026-03-20",
        check_in_time="15:00",
        check_out_time="11:00",
        status="confirmed",
        guest_name="Alex Guest",
        nights=5,
        wifi_name="VillaSerenity_5G",
        wifi_password="sunny2026",
        access_code="4821",
        house_rules=[
            "No smoking indoors.",
            "Quiet hours 22:00 – 08:00.",
            "No parties or events.",
        ],
        emergency_contact="+66 80 000 0000",
        # Phase 666 fields
        extras_available=[
            ExtraItem(extra_id="ex-1", name="Motorbike Rental", description="125cc scooter", icon="🏍️", price=350.0),
            ExtraItem(extra_id="ex-2", name="Thai Massage", description="1-hour in-villa", icon="💆", price=500.0, category="wellness"),
        ],
        chat_enabled=True,
        property_latitude=9.5120,
        property_longitude=100.0136,
        ac_instructions="Remote on bedside table. Set to 25°C for comfort.",
        hot_water_info="Electric heater — switch on 15 min before use.",
        parking_info="1 covered spot in front of villa. No street parking.",
        pool_instructions="Pool cleaned daily at 8 AM. No glass near pool.",
        trash_instructions="Separate bins in kitchen: recycle (green), general (black).",
    ),
}


def stub_lookup(booking_ref: str) -> GuestBookingView | None:
    return _STUB_BOOKINGS.get(booking_ref)
