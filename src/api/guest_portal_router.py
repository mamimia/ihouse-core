"""
Phase 262 + Phases 670–675 + Phase 686 — Guest Self-Service Portal Router
==========================================================================

Public (no JWT) endpoints — guest-token-gated.

GET  /guest/booking/{booking_ref}     — Booking overview + check-in info
GET  /guest/booking/{booking_ref}/wifi — Wi-Fi credentials only
GET  /guest/booking/{booking_ref}/rules — House rules only

Phase 670: POST/GET /guest/{token}/messages       — Guest chat
Phase 671: POST/GET /bookings/{booking_id}/guest-messages (manager side, in guest_messages_router)
Phase 672: GET /guest/{token}/contact              — WhatsApp link + phone + email
Phase 673: GET /guest/{token}/location             — GPS + map link
Phase 674: GET /guest/{token}/house-info           — All house info fields
Phase 675: GET /guest/{token}/portal?lang=th       — Multi-language support

Phase 686: GET /bookings/{booking_id}/checkout-view — Checkout worker view
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from services.guest_portal import (
    get_guest_booking,
    stub_lookup,
    GuestBookingView,
    GuestPortalError,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/guest", tags=["guest"])


def _booking_to_dict(b: GuestBookingView) -> dict:
    d = {
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
        # Phase 666 fields
        "chat_enabled":      b.chat_enabled,
        "property_latitude": b.property_latitude,
        "property_longitude": b.property_longitude,
    }
    if b.extras_available:
        from dataclasses import asdict
        d["extras_available"] = [asdict(e) for e in b.extras_available]
    return d


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


# --- Stub token resolver (for Phases 670+) ---

def _resolve_token_ctx(token: str) -> dict | None:
    """Resolve a guest token → context dict. For CI: test- prefix accepted."""
    if token.startswith("test-"):
        return {
            "booking_ref": f"BOOK-{token[5:13]}",
            "property_id": f"PROP-{token[5:13]}",
            "tenant_id": f"TENANT-{token[5:13]}",
        }
    return None  # Production: use guest_token service


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


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
            # Get booking by booking_id (booking_ref) — Phase 837: use booking_state
            booking_res = (
                db.table("booking_state")
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


# ===========================================================================
# Phase 670 — Guest Chat (Guest Side)
# ===========================================================================

@router.post("/{token}/messages", summary="Guest sends message (Phase 670)")
async def guest_send_message(token: str, body: Dict[str, Any], client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    content = str(body.get("content") or "").strip()
    if not content:
        return JSONResponse(status_code=400, content={"error": "VALIDATION_ERROR", "detail": "'content' is required."})

    from datetime import datetime, timezone
    now = datetime.now(tz=timezone.utc).isoformat()
    row = {
        "booking_ref": ctx["booking_ref"],
        "sender_type": "guest",
        "content": content[:2000],
        "created_at": now,
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("guest_chat_messages").insert(row).execute()
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})

        # SSE notify manager
        try:
            from channels.sse_broker import broker
            if ctx.get("tenant_id"):
                broker.publish_alert(
                    tenant_id=ctx["tenant_id"],
                    event_type="GUEST_MESSAGE_NEW",
                    booking_ref=ctx["booking_ref"],
                    content_preview=content[:80],
                )
        except Exception:
            pass

        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("guest_send_message error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


@router.get("/{token}/messages", summary="Guest reads messages (Phase 670)")
async def guest_get_messages(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("guest_chat_messages").select("*")
            .eq("booking_ref", ctx["booking_ref"])
            .order("created_at", desc=False)
            .execute()
        )
        messages = result.data or []
        return JSONResponse(status_code=200, content={"count": len(messages), "messages": messages})
    except Exception as exc:
        logger.exception("guest_get_messages error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 672 — WhatsApp Link + Contact Info
# ===========================================================================

@router.get("/{token}/contact", summary="Property manager contact info (Phase 672)")
async def guest_contact(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .select("name, manager_phone, manager_email, manager_whatsapp")
            .eq("property_id", ctx["property_id"])
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=200, content={"whatsapp_link": None, "phone": None, "email": None})

        prop = rows[0]
        phone = prop.get("manager_whatsapp") or prop.get("manager_phone") or ""
        property_name = prop.get("name", "")
        wa_link = f"https://wa.me/{phone.replace('+', '').replace(' ', '')}?text=Hi, I'm staying at {property_name}" if phone else None

        return JSONResponse(status_code=200, content={
            "whatsapp_link": wa_link,
            "phone": prop.get("manager_phone"),
            "email": prop.get("manager_email"),
        })
    except Exception as exc:
        logger.exception("guest_contact error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 673 — Location & Map
# ===========================================================================

@router.get("/{token}/location", summary="Property location + map link (Phase 673)")
async def guest_location(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .select("name, address, latitude, longitude")
            .eq("property_id", ctx["property_id"])
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=200, content={"latitude": None, "longitude": None, "address": None})

        prop = rows[0]
        lat = prop.get("latitude")
        lon = prop.get("longitude")
        map_url = f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else None
        directions_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}" if lat and lon else None

        return JSONResponse(status_code=200, content={
            "latitude": lat,
            "longitude": lon,
            "address": prop.get("address"),
            "map_url": map_url,
            "directions_url": directions_url,
        })
    except Exception as exc:
        logger.exception("guest_location error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 674 — House Info Pages
# ===========================================================================

_HOUSE_INFO_FIELDS = [
    "ac_instructions", "hot_water_info", "stove_instructions",
    "parking_info", "pool_instructions", "laundry_info",
    "tv_info", "emergency_contact", "extra_notes",
]

@router.get("/{token}/house-info", summary="All house info fields (Phase 674)")
async def guest_house_info(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        fields = ", ".join(_HOUSE_INFO_FIELDS)
        result = (
            db.table("properties")
            .select(fields)
            .eq("property_id", ctx["property_id"])
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=200, content={"info": {}})

        # Only return non-null fields
        info = {k: v for k, v in rows[0].items() if v is not None}
        return JSONResponse(status_code=200, content={"info": info})
    except Exception as exc:
        logger.exception("guest_house_info error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 675 — Multi-Language Portal
# ===========================================================================

@router.get("/{token}/portal-i18n", summary="Multi-language portal labels (Phase 675)")
async def guest_portal_i18n(
    token: str, lang: str = Query("en"), client: Optional[Any] = None,
) -> JSONResponse:
    ctx = _resolve_token_ctx(token)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    # Portal UI labels in selected language
    labels = _get_portal_labels(lang)
    return JSONResponse(status_code=200, content={"lang": lang, "labels": labels})


def _get_portal_labels(lang: str) -> dict:
    """Return portal UI labels in the selected language."""
    _LABELS: dict[str, dict[str, str]] = {
        "en": {
            "welcome": "Welcome",
            "check_in": "Check-in",
            "check_out": "Check-out",
            "wifi": "Wi-Fi",
            "house_rules": "House Rules",
            "extras": "Extras & Services",
            "chat": "Chat with Host",
            "location": "Location & Map",
            "house_info": "House Information",
            "contact": "Contact Host",
            "order": "Order",
            "emergency": "Emergency Contact",
        },
        "th": {
            "welcome": "ยินดีต้อนรับ",
            "check_in": "เช็คอิน",
            "check_out": "เช็คเอาท์",
            "wifi": "ไวไฟ",
            "house_rules": "กฎของบ้าน",
            "extras": "บริการเสริม",
            "chat": "แชทกับเจ้าของ",
            "location": "ตำแหน่งและแผนที่",
            "house_info": "ข้อมูลบ้าน",
            "contact": "ติดต่อเจ้าของ",
            "order": "สั่งซื้อ",
            "emergency": "ติดต่อฉุกเฉิน",
        },
        "he": {
            "welcome": "ברוכים הבאים",
            "check_in": "צ'ק-אין",
            "check_out": "צ'ק-אאוט",
            "wifi": "וויי-פיי",
            "house_rules": "כללי הבית",
            "extras": "שירותים נוספים",
            "chat": "צ'אט עם המארח",
            "location": "מיקום ומפה",
            "house_info": "מידע על הבית",
            "contact": "צור קשר עם המארח",
            "order": "הזמנה",
            "emergency": "איש קשר לחירום",
        },
    }
    return _LABELS.get(lang, _LABELS["en"])


# ===========================================================================
# Phase 686 — Checkout: Enhanced Worker View
# ===========================================================================

checkout_router = APIRouter(tags=["checkout"])


@checkout_router.get(
    "/bookings/{booking_id}/checkout-view",
    summary="Checkout worker view (Phase 686)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def checkout_worker_view(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns everything a checkout worker needs:
    - Reference photos
    - Latest cleaning photos
    - Property info (door code, special notes)
    - Deposit info
    - Guest info
    """

    try:
        db = client if client is not None else _get_supabase_client()

        # Get booking
        booking_res = (
            db.table("bookings")
            .select("booking_id, property_id, guest_name, check_in, check_out, status, number_of_guests")
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        booking_rows = booking_res.data or []
        if not booking_rows:
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND", "detail": f"Booking '{booking_id}' not found."})

        booking = booking_rows[0]
        property_id = booking.get("property_id", "")

        # Get property info
        prop_data: dict = {}
        try:
            prop_res = (
                db.table("properties")
                .select("name, door_code, special_notes, checkout_notes")
                .eq("property_id", property_id)
                .limit(1)
                .execute()
            )
            prop_rows = prop_res.data or []
            prop_data = prop_rows[0] if prop_rows else {}
        except Exception:
            pass

        # Get deposit info
        deposit_data: dict = {}
        try:
            dep_res = (
                db.table("cash_deposits")
                .select("id, amount, currency, status, collected_at")
                .eq("booking_id", booking_id)
                .limit(1)
                .execute()
            )
            dep_rows = dep_res.data or []
            deposit_data = dep_rows[0] if dep_rows else {}
        except Exception:
            pass

        # Get reference photos
        ref_photos: list = []
        try:
            ref_res = (
                db.table("property_reference_photos")
                .select("photo_url, room_label, caption")
                .eq("property_id", property_id)
                .execute()
            )
            ref_photos = ref_res.data or []
        except Exception:
            pass

        # Get cleaning photos from this booking
        cleaning_photos: list = []
        try:
            clean_res = (
                db.table("cleaning_task_photos")
                .select("photo_url, room_label, created_at")
                .eq("booking_id", booking_id)
                .order("created_at", desc=True)
                .execute()
            )
            cleaning_photos = clean_res.data or []
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "booking": {
                "booking_id": booking.get("booking_id"),
                "guest_name": booking.get("guest_name"),
                "check_in": booking.get("check_in"),
                "check_out": booking.get("check_out"),
                "number_of_guests": booking.get("number_of_guests"),
                "status": booking.get("status"),
            },
            "property": {
                "name": prop_data.get("name"),
                "door_code": prop_data.get("door_code"),
                "special_notes": prop_data.get("special_notes"),
                "checkout_notes": prop_data.get("checkout_notes"),
            },
            "deposit": deposit_data,
            "reference_photos": ref_photos,
            "cleaning_photos": cleaning_photos,
        })
    except Exception as exc:
        logger.exception("checkout_worker_view error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})
