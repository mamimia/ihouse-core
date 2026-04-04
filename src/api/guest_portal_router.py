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
from datetime import datetime, timezone, date as date_type
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
from services.guest_token import resolve_guest_token_context

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


# --- Token context resolver (delegates to canonical service) ---

def _resolve_token_ctx(token: str, client: Any | None = None) -> dict | None:
    """Resolve guest token → context dict via canonical service."""
    ctx = resolve_guest_token_context(token, db=client)
    if ctx is None:
        return None
    return ctx.to_dict()


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
    summary="Guest portal via token URL (Phase 400, enriched Phase 64)",
    tags=["guest"],
)
async def guest_portal_by_token(token: str, client: Optional[Any] = None) -> JSONResponse:
    """
    GET /guest/portal/{token}

    Public endpoint. Token is in the URL path (from QR code / link).
    Verifies the guest token via canonical resolver, looks up property data,
    and returns the GuestPortalData the frontend expects.

    Phase 64 enrichment: also returns booking context for the Current Stay
    portal structure (guest_name, check_in, check_out, status,
    number_of_guests, deposit_status, checkout_notes).
    """
    # Get DB client (injectable for testing)
    try:
        db = client if client is not None else _get_supabase_client()
    except Exception:
        db = None

    # 1. Verify token via canonical resolver
    ctx = resolve_guest_token_context(token, db=db)
    if ctx is None:
        return JSONResponse(status_code=401, content={
            "error": "TOKEN_INVALID",
            "message": "This link is invalid or has expired. Please contact your host.",
        })

    booking_ref = ctx.booking_ref
    property_id = ctx.property_id

    # 2. Look up property + booking data
    if db:
        try:
            # 2a. Resolve property_id + guest_id from booking_state
            guest_id_from_state: Optional[str] = None
            bs_res = (
                db.table("booking_state")
                .select("property_id, guest_id, guest_name")
                .eq("booking_id", booking_ref)
                .limit(1)
                .execute()
            )
            if bs_res.data:
                bs_row = bs_res.data[0]
                if not property_id:
                    property_id = bs_row.get("property_id", "")
                guest_id_from_state = bs_row.get("guest_id")

            # 2b. Property info
            prop_data: dict = {}
            if property_id:
                try:
                    prop_res = (
                        db.table("properties")
                        # 1047A ROOT FIX: align to actual schema (no 'name', no 'check_in_time' etc.)
                        # Phase 1047B: add portal_host_* (guest-facing display layer only)
                        .select("property_id, display_name, address, wifi_name, wifi_password, "
                                "checkin_time, checkout_time, house_rules, "
                                "emergency_contact, description, extra_notes, "
                                "cover_photo_url, "
                                "portal_host_name, portal_host_photo_url, portal_host_intro")
                        .eq("property_id", property_id)
                        .limit(1)
                        .execute()
                    )
                    if prop_res.data:
                        prop_data = prop_res.data[0]
                except Exception:
                    pass

            # 2c. Phase 64 — Booking context for Welcome/Stay Header + Your Stay
            booking_data: dict = {}
            try:
                b_res = (
                    db.table("bookings")
                    .select("booking_id, guest_name, check_in, check_out, "
                            "status, number_of_guests")
                    .eq("booking_id", booking_ref)
                    .limit(1)
                    .execute()
                )
                if b_res.data:
                    booking_data = b_res.data[0]
            except Exception:
                pass

            # 2c-2. Phase 949d-2 — Canonical guest identity resolution
            # When guest_id exists (set by document intake at Step 2),
            # resolve guests.full_name as the canonical name.
            # Critical for iCal bookings where booking-level guest_name
            # may be "Reserved" or "Airbnb (Not available)".
            canonical_guest_name = booking_data.get("guest_name")
            if guest_id_from_state:
                try:
                    guest_res = (
                        db.table("guests")
                        .select("full_name")
                        .eq("id", guest_id_from_state)
                        .limit(1)
                        .execute()
                    )
                    if guest_res.data and guest_res.data[0].get("full_name"):
                        canonical_guest_name = guest_res.data[0]["full_name"]
                except Exception:
                    pass  # fall back to booking-level name

            # Phase 1047A-name: sanitize OTA platform placeholder names
            # These are internal platform strings that must not be shown to guests.
            _OTA_PLACEHOLDER_NAMES = {
                'reserved', 'airbnb (not available)', 'not available',
                'guest', 'traveler', 'traveller', 'vrbo guest',
            }
            if canonical_guest_name and canonical_guest_name.lower().strip() in _OTA_PLACEHOLDER_NAMES:
                canonical_guest_name = None  # frontend will show generic 'Welcome'

            # 2d. Phase 64 — Deposit status for Your Stay section
            deposit_status: Optional[str] = None
            try:
                dep_res = (
                    db.table("cash_deposits")
                    .select("status")
                    .eq("booking_id", booking_ref)
                    .limit(1)
                    .execute()
                )
                if dep_res.data:
                    deposit_status = dep_res.data[0].get("status")
            except Exception:
                pass

            return JSONResponse(status_code=200, content={
                # Section 1 — Welcome / Stay Header
                "guest_name": canonical_guest_name,
                "check_in": booking_data.get("check_in"),
                "check_out": booking_data.get("check_out"),
                "booking_status": booking_data.get("status"),
                "cover_photo_url": prop_data.get("cover_photo_url"),  # Phase 1047A
                # Section 2 — Home Essentials
                # Phase 1047A-name ROOT FIX: read 'display_name', not 'name' (column does not exist).
                # Backend returns None when missing — frontend renders 'Your Villa'.
                "property_name": prop_data.get("display_name") or None,
                "property_address": prop_data.get("address"),
                "wifi_name": prop_data.get("wifi_name"),
                "wifi_password": prop_data.get("wifi_password"),
                # 1047A ROOT FIX: actual columns are checkin_time / checkout_time
                "check_in_time": prop_data.get("checkin_time", "15:00"),
                "check_out_time": prop_data.get("checkout_time", "11:00"),
                "house_rules": prop_data.get("house_rules") or [],
                "emergency_contact": prop_data.get("emergency_contact"),
                # 1047A ROOT FIX: no welcome_message column — use description
                "welcome_message": prop_data.get("description"),
                # Section 6 — Your Stay
                # 1047A ROOT FIX: no checkout_notes column — use extra_notes
                "number_of_guests": booking_data.get("number_of_guests"),
                "deposit_status": deposit_status,
                "checkout_notes": prop_data.get("extra_notes"),
                # Phase 1047B — Guest Portal Host Identity (display layer only, not routing truth)
                "portal_host_name":      prop_data.get("portal_host_name") or None,
                "portal_host_photo_url": prop_data.get("portal_host_photo_url") or None,
                "portal_host_intro":     prop_data.get("portal_host_intro") or None,
            })
        except Exception:
            pass  # Fall through to fallback

    # 3. Fallback: token is valid but DB not available — return minimal data.
    # Phase 1047A-name: DO NOT include booking_ref or property_id in property_name.
    # Frontend guard renders 'Your Villa' when property_name is None.
    return JSONResponse(status_code=200, content={
        "property_name": None,
        "check_in_time": "15:00",
        "check_out_time": "11:00",
        "house_rules": [],
    })


# ===========================================================================
# Phase 670 — Guest Chat (Guest Side)
# ===========================================================================

@router.post("/{token}/messages", summary="Guest sends message (Phase 670)")
async def guest_send_message(token: str, body: Dict[str, Any], client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token, client=client)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    content = str(body.get("content") or "").strip()
    if not content:
        return JSONResponse(status_code=400, content={"error": "VALIDATION_ERROR", "detail": "'content' is required."})

    # Validate token context has both required NOT NULL fields before attempting insert
    booking_id = ctx.get("booking_ref", "")
    property_id = ctx.get("property_id", "")
    tenant_id = ctx.get("tenant_id", "")
    if not booking_id or not property_id:
        logger.warning("guest_send_message: incomplete token context — booking_ref=%r property_id=%r", booking_id, property_id)
        return JSONResponse(status_code=500, content={"error": "CONTEXT_ERROR", "detail": "Token context incomplete."})

    # Phase 1048: Resolve the canonical conversation owner (OM or admin fallback).
    # This stamps assigned_om_id at insert time — the routing truth for inbox/dossier/reassignment.
    # Resolution failure is non-blocking: guest send succeeds even if OM lookup fails.
    try:
        db = client if client is not None else _get_supabase_client()
        from services.guest_messaging import resolve_conversation_owner
        assigned_om_id = resolve_conversation_owner(db, property_id, tenant_id)
    except Exception as exc:
        logger.warning("guest_send_message: owner resolution failed (non-blocking): %s", exc)
        assigned_om_id = tenant_id  # last-resort fallback
        db = client if client is not None else _get_supabase_client()

    # Phase 1047C + 1048: canonical insert row
    # Columns: booking_id, property_id, tenant_id, sender_type, message, assigned_om_id
    # booking_ref from token IS the booking_id value in this table
    row = {
        "booking_id":    booking_id,
        "property_id":   property_id,
        "tenant_id":     tenant_id,
        "sender_type":   "guest",
        "message":       content[:2000],
        "assigned_om_id": assigned_om_id,
    }

    try:
        result = db.table("guest_chat_messages").insert(row).execute()
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})

        # SSE notify manager — best-effort, non-blocking
        try:
            from channels.sse_broker import broker
            if tenant_id:
                broker.publish_alert(
                    tenant_id=tenant_id,
                    event_type="GUEST_MESSAGE_NEW",
                    booking_ref=booking_id,
                    assigned_om_id=assigned_om_id,
                    content_preview=content[:80],
                )
        except Exception:
            pass

        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("guest_send_message error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


@router.get("/{token}/messages", summary="Guest reads thread history (Phase 670 / 1053)")
async def guest_get_messages(token: str, client: Optional[Any] = None) -> JSONResponse:
    """
    Returns the conversation thread for the guest's current stay.

    Scoped: booking_id from token context only — one stay, no cross-stay leakage.
    Returns: sender_type, message, created_at, id.
    Internal fields (assigned_om_id, sender_id, tenant_id) are stripped — NOT exposed to guest.
    Host messages are labeled with portal_host_name from property context (Phase 1053).

    Phase 1052 identity rule:
        sender_id = user_id (NOT tenant_id).
        This field is not returned to guest; it is internal routing truth only.
    """
    ctx = _resolve_token_ctx(token, client=client)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    booking_id = ctx.get("booking_ref", "")
    if not booking_id:
        return JSONResponse(status_code=400, content={"error": "TOKEN_CONTEXT_INCOMPLETE"})

    try:
        db = client if client is not None else _get_supabase_client()

        # Phase 1053 fix: column is booking_id, NOT booking_ref
        # Previous version used .eq("booking_ref", ...) which always returned 0 rows.
        result = (
            db.table("guest_chat_messages")
            .select("id,sender_type,message,created_at")
            .eq("booking_id", booking_id)   # FIXED: was "booking_ref" (wrong column name)
            .order("created_at", desc=False)
            .execute()
        )
        messages = result.data or []

        # Resolve portal_host_name for host message labeling (display layer, not routing truth)
        portal_host_name: str | None = None
        try:
            prop_res = (
                db.table("properties")
                .select("portal_host_name")
                .eq("property_id", ctx.get("property_id", ""))
                .limit(1)
                .execute()
            )
            if prop_res.data:
                portal_host_name = prop_res.data[0].get("portal_host_name") or None
        except Exception:
            pass

        # Return only guest-safe fields — strip all internal routing fields
        safe_messages = [
            {
                "id":          m["id"],
                "sender_type": m["sender_type"],
                "message":     m["message"],
                "created_at":  m.get("created_at"),
            }
            for m in messages
        ]

        return JSONResponse(status_code=200, content={
            "count":            len(safe_messages),
            "messages":         safe_messages,
            "portal_host_name": portal_host_name or "Your Host",
        })
    except Exception as exc:
        logger.exception("guest_get_messages error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 672 — WhatsApp Link + Contact Info
# ===========================================================================

@router.get("/{token}/contact", summary="Property manager contact info (Phase 672)")
async def guest_contact(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token, client=client)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            # 1047A ROOT FIX: actual columns are owner_phone, owner_email
            # manager_phone / manager_email / manager_whatsapp do not exist in schema
            .select("display_name, owner_phone, owner_email")
            .eq("property_id", ctx["property_id"])
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return JSONResponse(status_code=200, content={"whatsapp_link": None, "phone": None, "email": None})

        prop = rows[0]
        phone = prop.get("owner_phone") or ""
        # 1047A-name: use actual display_name or guest-safe fallback in WhatsApp pre-fill
        human_prop_name = prop.get("display_name") or "your villa"
        wa_link = (
            f"https://wa.me/{phone.replace('+', '').replace(' ', '')}"
            f"?text=Hi%2C+I%27m+a+guest+staying+at+{human_prop_name.replace(' ', '+')}"
            if phone else None
        )

        return JSONResponse(status_code=200, content={
            "whatsapp_link": wa_link,
            "phone": prop.get("owner_phone"),
            "email": prop.get("owner_email"),
        })
    except Exception as exc:
        logger.exception("guest_contact error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 673 — Location & Map
# ===========================================================================

@router.get("/{token}/location", summary="Property location + map link (Phase 673)")
async def guest_location(token: str, client: Optional[Any] = None) -> JSONResponse:
    ctx = _resolve_token_ctx(token, client=client)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            # Phase 1047C: removed non-existent 'name' column — address/latitude/longitude confirmed to exist
            .select("address, latitude, longitude")
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
    ctx = _resolve_token_ctx(token, client=client)
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
    ctx = _resolve_token_ctx(token, client=client)
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

        # Phase 949d-2: Resolve canonical guest name via guest_id
        canonical_guest_name = booking.get("guest_name")
        try:
            bs_res = (
                db.table("booking_state")
                .select("guest_id")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            guest_id = (bs_res.data[0].get("guest_id") if bs_res.data else None)
            if guest_id:
                guest_res = (
                    db.table("guests")
                    .select("full_name")
                    .eq("id", guest_id)
                    .limit(1)
                    .execute()
                )
                if guest_res.data and guest_res.data[0].get("full_name"):
                    canonical_guest_name = guest_res.data[0]["full_name"]
        except Exception:
            pass  # fall back to booking-level name

        # Get property info
        prop_data: dict = {}
        try:
            prop_res = (
                db.table("properties")
                # Phase 1047C: align to actual DB schema
                # name → display_name (name column does not exist)
                # special_notes → does not exist, removed
                # checkout_notes → extra_notes (checkout_notes does not exist)
                # door_code → confirmed to exist
                .select("display_name, door_code, extra_notes")
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
                "guest_name": canonical_guest_name,
                "check_in": booking.get("check_in"),
                "check_out": booking.get("check_out"),
                "number_of_guests": booking.get("number_of_guests"),
                "status": booking.get("status"),
            },
            "property": {
                "name": prop_data.get("display_name"),   # Phase 1047C: was prop_data.get("name") — column does not exist
                "door_code": prop_data.get("door_code"),
                "checkout_notes": prop_data.get("extra_notes"),  # Phase 1047C: was checkout_notes — column does not exist
            },
            "deposit": deposit_data,
            "reference_photos": ref_photos,
            "cleaning_photos": cleaning_photos,
        })
    except Exception as exc:
        logger.exception("checkout_worker_view error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ===========================================================================
# Phase 1065 — Guest Portal Early Checkout + Self Checkout Status
# ===========================================================================

def _now_iso_portal() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _generate_guest_checkout_url(db: Any, booking_state: dict, effective_checkout_date_str: str) -> Optional[str]:
    """
    Phase 1065B token fix.

    Auto-generate a GUEST_CHECKOUT token for the given booking and return its
    portal URL. Called only when self_checkout_eligible=True so the Self Check-Out
    CTA in the guest portal links to the wizard with the correct token type.

    The GUEST_PORTAL token the guest used to open the main portal is a DIFFERENT
    token type and is rejected by _verify_guest_checkout_token in the wizard.
    This function issues the correct type transparently, without requiring any
    operator action.

    Returns the full wizard URL, or None if generation fails (non-fatal — the CTA
    will fall back gracefully in the frontend).
    """
    try:
        from services.access_token_service import TokenType, issue_access_token, record_token

        booking_id = booking_state.get("booking_id", "")
        tenant_id  = booking_state.get("tenant_id", "")
        guest_id   = booking_state.get("guest_id") or ""

        # Compute TTL: same logic as _compute_token_ttl in guest_checkout_router.py
        GRACE   = __import__("datetime").timedelta(hours=4)
        MINIMUM = 3600
        now     = datetime.now(tz=timezone.utc)

        ttl_seconds: int = MINIMUM
        # Path 1: precise effective_at
        eff_at_raw = booking_state.get("early_checkout_effective_at")
        if eff_at_raw and booking_state.get("early_checkout_approved"):
            try:
                eff = datetime.fromisoformat(str(eff_at_raw).replace("Z", "+00:00"))
                if eff.tzinfo is None:
                    eff = eff.replace(tzinfo=timezone.utc)
                computed = max(int((eff + GRACE - now).total_seconds()), MINIMUM)
                ttl_seconds = computed
            except Exception:
                pass
        # Path 2: date string
        if ttl_seconds == MINIMUM and effective_checkout_date_str:
            try:
                from datetime import date as _d
                co = _d.fromisoformat(effective_checkout_date_str)
                co_dt = datetime(co.year, co.month, co.day, 11, 0, 0, tzinfo=timezone.utc)
                computed = max(int((co_dt + GRACE - now).total_seconds()), MINIMUM)
                ttl_seconds = computed
            except Exception:
                pass

        raw_token, exp = issue_access_token(
            token_type=TokenType.GUEST_CHECKOUT,
            entity_id=booking_id,
            email=str(guest_id),
            ttl_seconds=ttl_seconds,
        )

        import hashlib
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        record_token(
            tenant_id=tenant_id,
            token_type=TokenType.GUEST_CHECKOUT,
            entity_id=booking_id,
            raw_token=raw_token,
            exp=exp,
            email=str(guest_id),
            metadata={
                "booking_id":    booking_id,
                "generated_by":  "guest_portal_auto",
                "auto_generated": True,
            },
            db=db,
        )

        try:
            db.table("booking_state").update({
                "guest_checkout_token_hash": token_hash,
            }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()
        except Exception as exc:
            logger.warning("guest_checkout_status: token_hash write failed (non-fatal): %s", exc)

        base_url = os.environ.get("NEXT_PUBLIC_SITE_URL", "https://domaniqo-staging.vercel.app").rstrip("/")
        return f"{base_url}/guest-checkout/{raw_token}"

    except Exception as exc:
        logger.warning("guest_checkout_status: auto token generation failed (non-fatal): %s", exc)
        return None


def _effective_checkout_from_state(booking_state: dict) -> str:
    """
    Return the effective checkout date string (YYYY-MM-DD).
    If early_checkout_approved and early_checkout_date exist, use those.
    Otherwise fall back to check_out from booking_state.
    """
    if booking_state.get("early_checkout_approved") and booking_state.get("early_checkout_date"):
        return str(booking_state["early_checkout_date"])[:10]
    return str(booking_state.get("check_out") or "")[:10]


def _self_checkout_eligible(effective_checkout_date_str: str, effective_at_str: Optional[str] = None) -> bool:
    """
    Self-checkout becomes available within the 24-hour window before the effective checkout.

    Priority:
      1. early_checkout_effective_at (precise TIMESTAMPTZ) — 24h before that moment
      2. effective checkout DATE assumed at 11:00 UTC — eligible from 11:00 UTC on the day before
    """
    now = datetime.now(tz=timezone.utc)

    # Path 1: precise effective datetime available
    if effective_at_str:
        try:
            eff = datetime.fromisoformat(str(effective_at_str).replace("Z", "+00:00"))
            if eff.tzinfo is None:
                eff = eff.replace(tzinfo=timezone.utc)
            window_start = eff - __import__("datetime").timedelta(hours=24)
            return now >= window_start
        except Exception:
            pass

    # Path 2: DATE only — assume 11:00 UTC checkout time
    if effective_checkout_date_str:
        try:
            co = date_type.fromisoformat(effective_checkout_date_str)
            checkout_dt = datetime(co.year, co.month, co.day, 11, 0, 0, tzinfo=timezone.utc)
            window_start = checkout_dt - __import__("datetime").timedelta(hours=24)
            return now >= window_start
        except Exception:
            pass

    return False


@router.get(
    "/{token}/checkout-status",
    summary="Guest checkout status — effective date, self-checkout eligibility, early checkout state (Phase 1065)",
)
async def guest_checkout_status(token: str, client: Optional[Any] = None) -> JSONResponse:
    """
    GET /guest/{token}/checkout-status

    Returns:
      - original_checkout_date: the original booking check_out DATE
      - effective_checkout_date: the real checkout date (early or original)
      - is_early_checkout: whether an early checkout is approved
      - early_checkout_status: none | requested | approved | completed
      - early_checkout_request_pending: whether guest has already submitted a request
      - self_checkout_eligible: true if now is within 24h of effective checkout
      - valid_early_request_dates: list of YYYY-MM-DD dates the guest can request
        (today up to but not including original checkout date; excludes past dates)
      - guest_checkout_confirmed: whether the guest has already confirmed departure

    Phase 1065: Used by the guest portal to decide which actions to show.
    Does NOT require the guest to be inside the checkout window to read.
    """
    ctx = _resolve_token_ctx(token, client=client)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    booking_id = ctx.get("booking_ref", "")
    if not booking_id:
        return JSONResponse(status_code=400, content={"error": "TOKEN_CONTEXT_INCOMPLETE"})

    try:
        db = client if client is not None else _get_supabase_client()

        bs_res = (
            db.table("booking_state")
            .select(
                "booking_id, tenant_id, guest_id, check_in, check_out, status, "
                "early_checkout_approved, early_checkout_date, early_checkout_effective_at, "
                "early_checkout_status, early_checkout_requested_at, "
                "guest_checkout_confirmed_at"
            )
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        rows = bs_res.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND"})

        bs = rows[0]
        original_checkout = str(bs.get("check_out") or "")[:10]
        effective_checkout = _effective_checkout_from_state(bs)
        effective_at = bs.get("early_checkout_effective_at")
        ec_status = bs.get("early_checkout_status") or "none"
        is_early_approved = bool(bs.get("early_checkout_approved"))
        already_requested = ec_status in ("requested", "approved", "completed")
        self_eligible = _self_checkout_eligible(effective_checkout, effective_at)
        guest_confirmed = bool(bs.get("guest_checkout_confirmed_at"))

        # Valid early request dates: today up to (not including) original checkout
        valid_dates: list[str] = []
        try:
            today = date_type.today()
            check_in_d  = date_type.fromisoformat(str(bs.get("check_in") or "")[:10])
            check_out_d = date_type.fromisoformat(original_checkout)
            start_d = max(today, check_in_d)
            cur = start_d
            while cur < check_out_d:
                valid_dates.append(cur.isoformat())
                cur = date_type.fromordinal(cur.toordinal() + 1)
        except Exception:
            pass

        # Phase 1065B token fix:
        # Auto-generate a GUEST_CHECKOUT token when the window is open.
        # The main portal runs on a GUEST_PORTAL token — a different type rejected
        # by the wizard. Issue the correct type here so the CTA URL works.
        checkout_portal_url: Optional[str] = None
        if self_eligible and not guest_confirmed:
            checkout_portal_url = _generate_guest_checkout_url(db, bs, effective_checkout)

        return JSONResponse(status_code=200, content={
            "booking_id":                       booking_id,
            "original_checkout_date":           original_checkout,
            "effective_checkout_date":          effective_checkout,
            "is_early_checkout_approved":       is_early_approved,
            "early_checkout_status":            ec_status,
            "already_requested_early_checkout": already_requested,
            "self_checkout_eligible":           self_eligible,
            "valid_early_request_dates":        valid_dates,
            "guest_checkout_confirmed":         guest_confirmed,
            "checkout_portal_url":              checkout_portal_url,
        })
    except Exception as exc:
        logger.exception("guest_checkout_status error booking=%s: %s", booking_id, exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


@router.post(
    "/{token}/request-early-checkout",
    summary="Guest requests early checkout (Phase 1065)",
)
async def guest_request_early_checkout(
    token: str,
    body: Dict[str, Any],
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /guest/{token}/request-early-checkout

    Guest requests to leave earlier than their original checkout date.

    Body:
        requested_date: YYYY-MM-DD — the date the guest wants to leave (required)
        reason: short free-text reason (optional, ≤200 chars)

    Behavior:
      1. Validates that requested_date is in the valid window
         (today or later, strictly before original check_out)
      2. Writes early_checkout_requested_at + early_checkout_status='requested'
         + early_checkout_request_source='guest_portal' to booking_state
      3. Posts a structured system-style chat message to guest_chat_messages
         so the OM instantly sees the request in their inbox thread
      4. Returns {status: 'request_received', requested_date, message_id}

    Idempotent-ish: if status is already 'requested', returns 200 with
    status='already_requested'. Does NOT re-send chat unless it's the first request.

    Phase 1065: This is a guest-originated intake. The request DOES NOT auto-approve.
    Admin / OM must still approve via the existing early_checkout_router.py path.
    """
    ctx = _resolve_token_ctx(token, client=client)
    if not ctx:
        return JSONResponse(status_code=401, content={"error": "TOKEN_INVALID"})

    booking_id = ctx.get("booking_ref", "")
    property_id = ctx.get("property_id", "")
    tenant_id = ctx.get("tenant_id", "")

    if not booking_id or not property_id:
        return JSONResponse(status_code=500, content={"error": "CONTEXT_ERROR", "detail": "Token context incomplete."})

    # Validate requested_date
    requested_date = (body.get("requested_date") or "").strip()[:10]
    if not requested_date or len(requested_date) != 10:
        return JSONResponse(status_code=400, content={
            "error": "VALIDATION_ERROR",
            "detail": "requested_date (YYYY-MM-DD) is required.",
        })

    reason = str(body.get("reason") or "").strip()[:200] or None

    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch booking_state
        bs_res = (
            db.table("booking_state")
            .select(
                "booking_id, tenant_id, status, check_in, check_out, "
                "early_checkout_status, early_checkout_requested_at"
            )
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        rows = bs_res.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "NOT_FOUND"})

        bs = rows[0]
        original_checkout = str(bs.get("check_out") or "")[:10]
        check_in_str = str(bs.get("check_in") or "")[:10]
        booking_status = (bs.get("status") or "").lower()
        ec_status = bs.get("early_checkout_status") or "none"

        # Guard: booking must be in-stay
        if booking_status not in ("checked_in", "active"):
            return JSONResponse(status_code=409, content={
                "error": "INVALID_STATE",
                "detail": f"Early checkout can only be requested during an active stay. "
                          f"Current status: {booking_status}",
            })

        # Guard: idempotent — if already requested (or approved), don't re-record
        if ec_status in ("requested", "approved", "completed"):
            return JSONResponse(status_code=200, content={
                "status": "already_requested",
                "early_checkout_status": ec_status,
                "booking_id": booking_id,
                "detail": "An early checkout request is already on record for this stay.",
            })

        # Validate the requested date is in the valid window
        try:
            req_d = date_type.fromisoformat(requested_date)
            today = date_type.today()
            check_in_d = date_type.fromisoformat(check_in_str) if check_in_str else today
            check_out_d = date_type.fromisoformat(original_checkout) if original_checkout else None

            if req_d < max(today, check_in_d):
                return JSONResponse(status_code=400, content={
                    "error": "INVALID_DATE",
                    "detail": f"Requested date {requested_date} is in the past. "
                              f"Please choose today ({today.isoformat()}) or later.",
                })
            if check_out_d and req_d >= check_out_d:
                return JSONResponse(status_code=400, content={
                    "error": "INVALID_DATE",
                    "detail": f"Requested date {requested_date} must be before your original "
                              f"checkout date ({original_checkout}). Use your original checkout for same-day departures.",
                })
        except (ValueError, TypeError):
            return JSONResponse(status_code=400, content={
                "error": "INVALID_DATE",
                "detail": f"Invalid date format: '{requested_date}'. Use YYYY-MM-DD.",
            })

        now = _now_iso_portal()

        # 1. Record early checkout request in booking_state
        ec_update = {
            "early_checkout_requested_at":   now,
            "early_checkout_request_source": "guest_portal",
            "early_checkout_request_note":   reason,
            "early_checkout_status":         "requested",
            "early_checkout_date":           requested_date,   # informational — not binding until approval
        }
        try:
            db.table("booking_state").update(ec_update).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()
        except Exception as exc:
            logger.warning("guest_request_early_checkout: booking_state update failed: %s", exc)

        # 2. Write a structured system-style chat message so the OM sees the request in their inbox
        date_fmt = requested_date  # YYYY-MM-DD — already validated
        try:
            req_d_parsed = date_type.fromisoformat(requested_date)
            date_fmt = req_d_parsed.strftime("%B %-d, %Y")  # e.g. "July 21, 2026"
        except Exception:
            pass

        reason_line = f"\nReason: {reason}" if reason else ""
        chat_content = (
            f"[Early Checkout Request]\n"
            f"The guest has requested to check out early.\n"
            f"Requested date: {date_fmt}{reason_line}\n"
            f"Please confirm or contact the guest to arrange the early departure."
        )

        # Resolve conversation owner (OM) — same pattern as guest_send_message
        try:
            from services.guest_messaging import resolve_conversation_owner
            assigned_om_id = resolve_conversation_owner(db, property_id, tenant_id)
        except Exception:
            assigned_om_id = tenant_id

        chat_row = {
            "booking_id":     booking_id,
            "property_id":    property_id,
            "tenant_id":      tenant_id,
            "sender_type":    "system",   # Distinct from 'guest' and 'host' — structured request
            "message":        chat_content,
            "assigned_om_id": assigned_om_id,
        }
        chat_result = None
        try:
            insert_res = db.table("guest_chat_messages").insert(chat_row).execute()
            chat_result = (insert_res.data or [None])[0]
        except Exception as exc:
            logger.warning("guest_request_early_checkout: chat insert failed (non-blocking): %s", exc)

        # SSE notify OM — best-effort
        try:
            from channels.sse_broker import broker
            if tenant_id:
                broker.publish_alert(
                    tenant_id=tenant_id,
                    event_type="GUEST_EARLY_CHECKOUT_REQUESTED",
                    booking_ref=booking_id,
                    assigned_om_id=assigned_om_id,
                    content_preview=f"Early checkout requested for {date_fmt}",
                )
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "status":                "request_received",
            "booking_id":            booking_id,
            "requested_date":        requested_date,
            "early_checkout_status": "requested",
            "message_id":            chat_result.get("id") if chat_result else None,
            "detail": (
                f"Your request to check out on {date_fmt} has been received. "
                "The team will review and confirm shortly. You will be contacted if we need anything."
            ),
        })

    except Exception as exc:
        logger.exception("guest_request_early_checkout booking=%s: %s", booking_id, exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})

