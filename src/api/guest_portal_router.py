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


# ---------------------------------------------------------------------------
# Phase 400 — Token-in-URL guest portal endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/portal/{token}",
    summary="Guest portal via token URL (Phase 400)",
    tags=["guest"],
)
async def guest_portal_by_token(token: str) -> JSONResponse:
    """
    GET /guest/portal/{token}

    Public endpoint. Token is in the URL path (from QR code / link).
    Verifies the guest token, extracts booking_ref, looks up property data,
    and returns the GuestPortalData the frontend expects.

    PII-scoped: only property info (wifi, rules, check-in/out times).
    No guest names, financial data, or internal booking details.
    """
    import os
    from services.guest_token import verify_guest_token, is_guest_token_revoked

    # 1. Verify token (crypto + expiry)
    #    We don't know the booking_ref yet — decode first to extract it
    from services.guest_token import _decode_token, _sign, _get_secret
    import hmac as hmac_mod
    import time

    decoded = _decode_token(token)
    if not decoded:
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_INVALID",
            "message": "This link is invalid or malformed.",
        })

    message, provided_sig = decoded

    # Validate HMAC
    try:
        secret = _get_secret()
    except RuntimeError:
        return JSONResponse(status_code=503, content={
            "error": "TOKEN_SECRET_NOT_CONFIGURED",
            "message": "Guest token verification is not configured.",
        })

    expected_sig = _sign(message, secret)
    if not hmac_mod.compare_digest(provided_sig, expected_sig):
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_INVALID",
            "message": "This link is invalid.",
        })

    # Parse message: booking_ref:email:exp
    parts = message.split(":", 2)
    if len(parts) != 3:
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_INVALID",
            "message": "This link is invalid.",
        })

    booking_ref, _email, exp_str = parts
    try:
        exp = int(exp_str)
    except ValueError:
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_INVALID",
            "message": "This link is invalid.",
        })

    if exp < int(time.time()):
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_EXPIRED",
            "message": "This link has expired. Please contact your host.",
        })

    # 2. Check DB revocation (best-effort)
    try:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
        db = create_client(url, key)

        if is_guest_token_revoked(db, token):
            return JSONResponse(status_code=401, content={
                "error": "TOKEN_REVOKED",
                "message": "This link has been revoked.",
            })
    except Exception:
        db = None  # If DB check fails, continue with HMAC-verified data

    # 3. Look up booking + property from Supabase
    if db:
        try:
            # Get booking by booking_id (booking_ref)
            booking_res = (
                db.table("bookings")
                .select("booking_id, property_id, check_in, check_out, status, source")
                .eq("booking_id", booking_ref)
                .limit(1)
                .execute()
            )
            booking_rows = booking_res.data or []

            if booking_rows:
                booking = booking_rows[0]
                property_id = booking.get("property_id", "")

                # Get property info
                prop_data: dict = {}
                if property_id:
                    try:
                        prop_res = (
                            db.table("properties")
                            .select("property_id, name, address, wifi_name, wifi_password, check_in_time, check_out_time, house_rules, emergency_contact, welcome_message")
                            .eq("property_id", property_id)
                            .limit(1)
                            .execute()
                        )
                        prop_rows = prop_res.data or []
                        if prop_rows:
                            prop_data = prop_rows[0]
                    except Exception:
                        pass

                return JSONResponse(status_code=200, content={
                    "property_name": prop_data.get("name", property_id),
                    "property_address": prop_data.get("address"),
                    "wifi_name": prop_data.get("wifi_name"),
                    "wifi_password": prop_data.get("wifi_password"),
                    "check_in_time": prop_data.get("check_in_time", "15:00"),
                    "check_out_time": prop_data.get("check_out_time", "11:00"),
                    "house_rules": prop_data.get("house_rules") or [],
                    "emergency_contact": prop_data.get("emergency_contact"),
                    "welcome_message": prop_data.get("welcome_message"),
                })
        except Exception:
            pass  # Fall through to stub/fallback

    # 4. Fallback: token is valid but DB not available — return minimal data
    return JSONResponse(status_code=200, content={
        "property_name": f"Property ({booking_ref})",
        "check_in_time": "15:00",
        "check_out_time": "11:00",
        "house_rules": [],
    })
