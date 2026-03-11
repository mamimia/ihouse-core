"""
Phase 262 — Guest Self-Service Portal Router
=============================================

Public (no JWT) endpoints — guest-token-gated.

GET  /guest/booking/{booking_ref}     — Booking overview + check-in info
GET  /guest/booking/{booking_ref}/wifi — Wi-Fi credentials only
GET  /guest/booking/{booking_ref}/rules — House rules only
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse

from services.guest_portal import (
    get_guest_booking,
    stub_lookup,
    GuestBookingView,
    GuestPortalError,
)

router = APIRouter(prefix="/guest", tags=["guest"])


def _booking_to_dict(b: GuestBookingView) -> dict:
    return {
        "booking_ref":       b.booking_ref,
        "property_name":     b.property_name,
        "property_address":  b.property_address,
        "check_in_date":     b.check_in_date,
        "check_out_date":    b.check_out_date,
        "check_in_time":     b.check_in_time,
        "check_out_time":    b.check_out_time,
        "status":            b.status,
        "guest_name":        b.guest_name,
        "nights":            b.nights,
        "wifi_name":         b.wifi_name,
        "wifi_password":     b.wifi_password,
        "access_code":       b.access_code,
        "house_rules":       b.house_rules,
        "emergency_contact": b.emergency_contact,
    }


def _resolve(booking_ref: str, guest_token: str) -> GuestBookingView:
    """Shared resolution — raises HTTP 401/404 on error."""
    result = get_guest_booking(
        booking_ref=booking_ref,
        guest_token=guest_token,
        lookup_fn=stub_lookup,
    )
    if isinstance(result, GuestPortalError):
        status = 401 if result.code == "token_invalid" else 404
        raise HTTPException(status_code=status, detail=result.message)
    return result


@router.get(
    "/booking/{booking_ref}",
    summary="Guest booking overview (check-in details, access code, WiFi, house rules)",
)
async def guest_booking_overview(
    booking_ref: str,
    x_guest_token: str = Header(alias="x-guest-token"),
) -> JSONResponse:
    """
    GET /guest/booking/{booking_ref}

    Full guest-facing booking view. Requires header: X-Guest-Token.
    """
    view = _resolve(booking_ref, x_guest_token)
    return JSONResponse(status_code=200, content=_booking_to_dict(view))


@router.get(
    "/booking/{booking_ref}/wifi",
    summary="Wi-Fi credentials for a booking",
)
async def guest_wifi(
    booking_ref: str,
    x_guest_token: str = Header(alias="x-guest-token"),
) -> JSONResponse:
    """
    GET /guest/booking/{booking_ref}/wifi

    Returns wi-fi name and password (or null if not configured).
    """
    view = _resolve(booking_ref, x_guest_token)
    return JSONResponse(status_code=200, content={
        "booking_ref": view.booking_ref,
        "wifi_name":   view.wifi_name,
        "wifi_password": view.wifi_password,
    })


@router.get(
    "/booking/{booking_ref}/rules",
    summary="House rules for a booking",
)
async def guest_rules(
    booking_ref: str,
    x_guest_token: str = Header(alias="x-guest-token"),
) -> JSONResponse:
    """
    GET /guest/booking/{booking_ref}/rules

    Returns the property's house rules list.
    """
    view = _resolve(booking_ref, x_guest_token)
    return JSONResponse(status_code=200, content={
        "booking_ref": view.booking_ref,
        "house_rules": view.house_rules,
    })
