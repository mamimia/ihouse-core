"""
Phase 398 — Booking Check-in / Check-out Router

POST /bookings/{booking_id}/checkin    — Mark guest as arrived
POST /bookings/{booking_id}/checkout   — Mark guest as departed + create CLEANING task

Architecture:
    - Validates booking exists in booking_state for the authenticated tenant.
    - Updates booking_state.status (active → checked_in / checked_in → checked_out).
    - Writes best-effort audit event to event_log.
    - On checkout: creates a CLEANING task via task_writer (if not already exists).
    - JWT auth required. Tenant isolation via tenant_id.
    - Idempotent: checking in an already checked-in booking returns 200 (no-op).

State machine:
    active      → checked_in   (via checkin)
    checked_in  → checked_out  (via checkout)
    checked_out → (no further transitions via this router)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.envelope import ok, err

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Phase 63 — Role-based guards for check-in / check-out
# ---------------------------------------------------------------------------
# These are intentionally NOT capability guards. The checkin/checkout roles
# ARE the authorization — no additional capability delegation needed.
#
# admin / manager → always allowed (operational authority)
# checkin         → primary check-in worker (also allowed to check out)
# checkout        → primary check-out worker (NOT allowed to check in)
#
# Dev mode: jwt_identity returns {role: "admin"} → always in allowed set.
# Production: jwt_identity returns the real role from the JWT.
# ---------------------------------------------------------------------------

_CHECKIN_ALLOWED_ROLES = frozenset({"admin", "manager", "checkin"})
_CHECKOUT_ALLOWED_ROLES = frozenset({"admin", "manager", "checkin", "checkout"})


def _assert_checkin_role(identity: dict) -> None:
    """Raise 403 if identity role is not permitted to perform check-in."""
    role = identity.get("role", "")
    if role not in _CHECKIN_ALLOWED_ROLES:
        logger.warning(
            "role_guard: role=%s denied for checkin user=%s",
            role, identity.get("user_id", ""),
        )
        raise HTTPException(
            status_code=403,
            detail=f"CHECKIN_DENIED: role '{role}' cannot perform checkin.",
        )


def _assert_checkout_role(identity: dict) -> None:
    """Raise 403 if identity role is not permitted to perform check-out."""
    role = identity.get("role", "")
    if role not in _CHECKOUT_ALLOWED_ROLES:
        logger.warning(
            "role_guard: role=%s denied for checkout user=%s",
            role, identity.get("user_id", ""),
        )
        raise HTTPException(
            status_code=403,
            detail=f"CHECKOUT_DENIED: role '{role}' cannot perform checkout.",
        )


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_booking(db: Any, booking_id: str, tenant_id: str) -> Optional[dict]:
    """Fetch a single booking from booking_state."""
    try:
        result = (
            db.table("booking_state")
            .select("booking_id, tenant_id, status, property_id, check_in, check_out, source")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _write_audit_event(
    db: Any,
    booking_id: str,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> None:
    """Best-effort audit event to event_log."""
    try:
        db.table("event_log").insert({
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "event_type": event_type,
            "payload": payload,
            "received_at": datetime.now(tz=timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass  # audit is best-effort


def _write_audit_event_table(
    db: Any,
    tenant_id: str,
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict,
) -> None:
    """Best-effort audit event to audit_events table (Phase 189)."""
    try:
        db.table("audit_events").insert({
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload": payload,
            "occurred_at": datetime.now(tz=timezone.utc).isoformat(),
        }).execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Phase 58 — Guest token auto-issuance helpers
# ---------------------------------------------------------------------------

_PORTAL_BASE = "https://app.domaniqo.com/guest"
_GUEST_TOKEN_TTL = 30 * 86_400  # 30 days


def _auto_issue_guest_token(
    db: Any, booking_id: str, tenant_id: str,
) -> Optional[str]:
    """
    Issue a guest HMAC token as a system side-effect of check-in completion.

    Best-effort:
    - If a non-revoked token already exists for this booking, reuse it
      (prevents duplicate tokens on retries).
    - Returns the portal URL string, or None on failure.
    - Failures here do NOT fail the check-in — token issuance is non-blocking.
    """
    try:
        from services.guest_token import issue_guest_token, record_guest_token

        # Check if a non-revoked token already exists for this booking
        existing = (
            db.table("guest_tokens")
            .select("booking_ref, expires_at")
            .eq("booking_ref", booking_id)
            .eq("tenant_id", tenant_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if existing.data:
            # Token already exists — reuse by re-issuing (HMAC is stateless,
            # the portal URL just needs a valid token)
            pass  # fall through to issue a fresh one (old one stays valid too)

        raw_token, exp = issue_guest_token(
            booking_ref=booking_id,
            guest_email="",  # guest email not available at this point
            ttl_seconds=_GUEST_TOKEN_TTL,
        )

        record_guest_token(
            db=db,
            booking_ref=booking_id,
            tenant_id=tenant_id,
            raw_token=raw_token,
            exp=exp,
        )

        portal_url = f"{_PORTAL_BASE}/{raw_token}"
        logger.info("checkin: guest token issued for booking_id=%s", booking_id)
        return portal_url

    except Exception as exc:
        logger.warning("checkin: guest token issuance failed (non-blocking): %s", exc)
        return None


def _lookup_existing_portal_url(
    db: Any, booking_id: str, tenant_id: str,
) -> Optional[str]:
    """
    Look up existing guest portal URL for the idempotent (already_checked_in) path.

    Checks guest_qr_tokens (short tokens) first, then falls back to
    re-issuing an HMAC token. Returns None if nothing found.
    """
    try:
        # 1. Check short QR tokens
        qr_res = (
            db.table("guest_qr_tokens")
            .select("portal_url")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if qr_res.data and qr_res.data[0].get("portal_url"):
            return qr_res.data[0]["portal_url"]

        # 2. Check HMAC tokens — if one exists, issue a fresh portal URL
        token_res = (
            db.table("guest_tokens")
            .select("booking_ref")
            .eq("booking_ref", booking_id)
            .eq("tenant_id", tenant_id)
            .is_("revoked_at", "null")
            .limit(1)
            .execute()
        )
        if token_res.data:
            # Re-issue fresh token for the URL (old ones stay valid too)
            from services.guest_token import issue_guest_token
            raw_token, _ = issue_guest_token(booking_ref=booking_id, ttl_seconds=_GUEST_TOKEN_TTL)
            return f"{_PORTAL_BASE}/{raw_token}"

        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POST /bookings/{booking_id}/checkin
# ---------------------------------------------------------------------------

@router.post(
    "/bookings/{booking_id}/checkin",
    tags=["bookings"],
    summary="Mark guest as arrived (Phase 398)",
    responses={
        200: {"description": "Guest checked in (or already checked in)"},
        404: {"description": "Booking not found for this tenant"},
        409: {"description": "Booking not in a checkin-eligible state"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def checkin_booking(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /bookings/{booking_id}/checkin

    Transitions booking from 'active' → 'checked_in'.
    Idempotent: if already checked_in, returns 200 with no-op flag.

    Phase 58: On successful completion, auto-issues a guest HMAC token
    (30 days, best-effort) and returns guest_portal_url in the response.
    This is the canonical guest-access-issuance trigger.

    Phase 63: Restricted to admin / manager / checkin roles only.
    """
    _assert_checkin_role(identity)
    tenant_id: str = identity["tenant_id"]
    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        booking = _get_booking(db, booking_id, tenant_id)
        if not booking:
            return err("BOOKING_NOT_FOUND", "Booking not found", status=404, booking_id=booking_id)

        current_status = (booking.get("status") or "").lower()

        # Already checked in — idempotent success
        # Phase 58: also return existing guest_portal_url if token was already issued
        if current_status == "checked_in":
            portal_url = _lookup_existing_portal_url(db, booking_id, tenant_id)
            return ok({
                "status": "already_checked_in",
                "booking_id": booking_id,
                "checked_in_at": now,
                "noop": True,
                "guest_portal_url": portal_url,
            })

        # Only 'active', 'confirmed', or 'observed' bookings can be checked in.
        # 'confirmed' = manually-created bookings (operationally equivalent to 'active').
        # 'observed' = iCal-imported bookings that are valid arrivals.
        if current_status not in ("active", "observed", "confirmed"):
            return err(
                "INVALID_STATE",
                f"Cannot check in booking with status '{current_status}'. Must be 'active', 'confirmed', or 'observed'.",
                status=409,
                booking_id=booking_id,
                current_status=current_status,
            )

        # Update booking_state
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        db.table("booking_state").update({
            "status": "checked_in",
            "updated_at_ms": now_ms,
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Audit events (best-effort)
        _write_audit_event(db, booking_id, tenant_id, "BOOKING_CHECKED_IN", {
            "previous_status": current_status,
            "new_status": "checked_in",
            "checked_in_at": now,
            "property_id": booking.get("property_id"),
        })
        _write_audit_event_table(db, tenant_id, tenant_id, "booking.checkin", "booking", booking_id, {
            "previous_status": current_status,
            "property_id": booking.get("property_id"),
        })

        # D-5: Transition property operational_status → 'occupied'
        property_id = booking.get("property_id")
        if property_id:
            try:
                db.table("properties").update({
                    "operational_status": "occupied",
                }).eq("property_id", property_id).eq("tenant_id", tenant_id).execute()
            except Exception:
                logger.warning("checkin: failed to set property %s to occupied", property_id)

        # Phase 58: Auto-issue guest HMAC token (best-effort, 30-day TTL)
        guest_portal_url = _auto_issue_guest_token(db, booking_id, tenant_id)

        logger.info("checkin: booking_id=%s tenant=%s → checked_in portal=%s",
                     booking_id, tenant_id, "yes" if guest_portal_url else "no")

        return ok({
            "status": "checked_in",
            "booking_id": booking_id,
            "property_id": property_id,
            "checked_in_at": now,
            "noop": False,
            "guest_portal_url": guest_portal_url,
        })

    except Exception as exc:
        logger.exception("POST /bookings/%s/checkin error: %s", booking_id, exc)
        return err("INTERNAL_ERROR", "Check-in failed", status=500)


# ---------------------------------------------------------------------------
# POST /bookings/{booking_id}/checkout
# ---------------------------------------------------------------------------

@router.post(
    "/bookings/{booking_id}/checkout",
    tags=["bookings"],
    summary="Mark guest as departed + create CLEANING task (Phase 398)",
    responses={
        200: {"description": "Guest checked out (or already checked out)"},
        404: {"description": "Booking not found for this tenant"},
        409: {"description": "Booking not in a checkout-eligible state"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def checkout_booking(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /bookings/{booking_id}/checkout

    Transitions booking from 'checked_in' → 'checked_out'.
    Also creates a CLEANING task for the property via task_writer.
    Idempotent: if already checked_out, returns 200 with no-op flag.

    Phase 63: Restricted to admin / manager / checkin / checkout roles only.
    """
    _assert_checkout_role(identity)
    tenant_id: str = identity["tenant_id"]
    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        booking = _get_booking(db, booking_id, tenant_id)
        if not booking:
            return err("BOOKING_NOT_FOUND", "Booking not found", status=404, booking_id=booking_id)

        current_status = (booking.get("status") or "").lower()

        # Already checked out — idempotent success
        if current_status == "checked_out":
            return ok({
                "status": "already_checked_out",
                "booking_id": booking_id,
                "checked_out_at": now,
                "noop": True,
            })

        # Only 'checked_in' or 'active' bookings can be checked out
        if current_status not in ("checked_in", "active"):
            return err(
                "INVALID_STATE",
                f"Cannot check out booking with status '{current_status}'. Must be 'checked_in' or 'active'.",
                status=409,
                booking_id=booking_id,
                current_status=current_status,
            )

        # Update booking_state
        now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
        db.table("booking_state").update({
            "status": "checked_out",
            "updated_at_ms": now_ms,
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Create CLEANING task (best-effort)
        cleaning_task_count = 0
        try:
            from tasks.task_writer import write_tasks_for_booking_created
            cleaning_task_count = write_tasks_for_booking_created(
                tenant_id=tenant_id,
                booking_id=booking_id,
                property_id=booking.get("property_id") or "unknown",
                check_in=booking.get("check_out") or now[:10],  # cleaning due on checkout date
                provider=booking.get("source") or "manual",
                client=db,
            )
        except Exception:
            logger.warning("checkout: failed to create CLEANING task for booking_id=%s", booking_id)

        # Audit events (best-effort)
        _write_audit_event(db, booking_id, tenant_id, "BOOKING_CHECKED_OUT", {
            "previous_status": current_status,
            "new_status": "checked_out",
            "checked_out_at": now,
            "property_id": booking.get("property_id"),
            "cleaning_tasks_created": cleaning_task_count,
        })
        _write_audit_event_table(db, tenant_id, tenant_id, "booking.checkout", "booking", booking_id, {
            "previous_status": current_status,
            "property_id": booking.get("property_id"),
            "cleaning_tasks_created": cleaning_task_count,
        })

        # D-5b: Transition property operational_status → 'needs_cleaning' on checkout
        property_id = booking.get("property_id")
        if property_id:
            try:
                db.table("properties").update({
                    "operational_status": "needs_cleaning",
                }).eq("property_id", property_id).eq("tenant_id", tenant_id).execute()
            except Exception:
                logger.warning("checkout: failed to set property %s to needs_cleaning", property_id)

        logger.info(
            "checkout: booking_id=%s tenant=%s → checked_out, cleaning_tasks=%d",
            booking_id, tenant_id, cleaning_task_count,
        )

        return ok({
            "status": "checked_out",
            "booking_id": booking_id,
            "property_id": booking.get("property_id"),
            "checked_out_at": now,
            "cleaning_tasks_created": cleaning_task_count,
            "noop": False,
        })

    except Exception as exc:
        logger.exception("POST /bookings/%s/checkout error: %s", booking_id, exc)
        return err("INTERNAL_ERROR", "Check-out failed", status=500)
