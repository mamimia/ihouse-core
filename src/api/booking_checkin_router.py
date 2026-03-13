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

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth

logger = logging.getLogger(__name__)

router = APIRouter()


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
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /bookings/{booking_id}/checkin

    Transitions booking from 'active' → 'checked_in'.
    Idempotent: if already checked_in, returns 200 with no-op flag.
    """
    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        booking = _get_booking(db, booking_id, tenant_id)
        if not booking:
            return JSONResponse(
                status_code=404,
                content={"error": "BOOKING_NOT_FOUND", "booking_id": booking_id},
            )

        current_status = (booking.get("status") or "").lower()

        # Already checked in — idempotent success
        if current_status == "checked_in":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "already_checked_in",
                    "booking_id": booking_id,
                    "checked_in_at": now,
                    "noop": True,
                },
            )

        # Only 'active' bookings can be checked in
        if current_status != "active":
            return JSONResponse(
                status_code=409,
                content={
                    "error": "INVALID_STATE",
                    "message": f"Cannot check in booking with status '{current_status}'. Must be 'active'.",
                    "booking_id": booking_id,
                    "current_status": current_status,
                },
            )

        # Update booking_state
        db.table("booking_state").update({
            "status": "checked_in",
            "updated_at": now,
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

        logger.info("checkin: booking_id=%s tenant=%s → checked_in", booking_id, tenant_id)

        return JSONResponse(
            status_code=200,
            content={
                "status": "checked_in",
                "booking_id": booking_id,
                "property_id": booking.get("property_id"),
                "checked_in_at": now,
                "noop": False,
            },
        )

    except Exception as exc:
        logger.exception("POST /bookings/%s/checkin error: %s", booking_id, exc)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "Check-in failed"},
        )


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
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /bookings/{booking_id}/checkout

    Transitions booking from 'checked_in' → 'checked_out'.
    Also creates a CLEANING task for the property via task_writer.
    Idempotent: if already checked_out, returns 200 with no-op flag.
    """
    now = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        booking = _get_booking(db, booking_id, tenant_id)
        if not booking:
            return JSONResponse(
                status_code=404,
                content={"error": "BOOKING_NOT_FOUND", "booking_id": booking_id},
            )

        current_status = (booking.get("status") or "").lower()

        # Already checked out — idempotent success
        if current_status == "checked_out":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "already_checked_out",
                    "booking_id": booking_id,
                    "checked_out_at": now,
                    "noop": True,
                },
            )

        # Only 'checked_in' or 'active' bookings can be checked out
        if current_status not in ("checked_in", "active"):
            return JSONResponse(
                status_code=409,
                content={
                    "error": "INVALID_STATE",
                    "message": f"Cannot check out booking with status '{current_status}'. Must be 'checked_in' or 'active'.",
                    "booking_id": booking_id,
                    "current_status": current_status,
                },
            )

        # Update booking_state
        db.table("booking_state").update({
            "status": "checked_out",
            "updated_at": now,
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

        logger.info(
            "checkout: booking_id=%s tenant=%s → checked_out, cleaning_tasks=%d",
            booking_id, tenant_id, cleaning_task_count,
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "checked_out",
                "booking_id": booking_id,
                "property_id": booking.get("property_id"),
                "checked_out_at": now,
                "cleaning_tasks_created": cleaning_task_count,
                "noop": False,
            },
        )

    except Exception as exc:
        logger.exception("POST /bookings/%s/checkout error: %s", booking_id, exc)
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "Check-out failed"},
        )
