"""
Admin Close Stay — POST /admin/bookings/{booking_id}/admin-close

Provides a safe admin-only resolution action for overdue bookings that were
never serviced by a worker checkout flow. This is distinct from a normal
checkout in every meaningful way:

  — Sets booking_state.status = 'admin_closed'  (NOT 'checked_out')
  — Does NOT set checked_out_at
  — Does NOT trigger settlement
  — Does NOT create or cancel any tasks
  — Does NOT emit BOOKING_CHECKED_OUT event
  — Writes one BOOKING_ADMIN_CLOSED audit event for full traceability

Eligibility: booking must be in an overdue state:
  status IN ('active', 'confirmed')
  AND check_out < today (UTC date)
  AND checked_out_at IS NULL

This endpoint is intentionally narrow. It exists only to give admins a
truthful way to clear stale OTA/iCal ghost bookings and manual confirmed
bookings that were never operationally serviced, without polluting settlement
records, worker history, or operational metrics with fake checkout data.

Auth: JWT required. Admin capability ('admin') required.
Invariant: read-only endpoints must never be used — only this endpoint may
           transition a booking to 'admin_closed'.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.capability_guard import require_capability
from api.envelope import ok, err
from services.audit_writer import write_audit_event

logger = logging.getLogger(__name__)

router = APIRouter()

_ELIGIBLE_STATUSES = frozenset({"active", "confirmed"})


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.post(
    "/admin/bookings/{booking_id}/admin-close",
    tags=["admin", "bookings"],
    summary="Admin Close Stay — resolve an overdue booking without triggering checkout side effects",
    responses={
        200: {"description": "Booking successfully marked admin_closed"},
        400: {"description": "Booking is not eligible for admin closure (not overdue)"},
        401: {"description": "Missing or invalid JWT"},
        403: {"description": "Insufficient capability (admin required)"},
        404: {"description": "Booking not found for this tenant"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def admin_close_booking(
    booking_id: str,
    body: dict = None,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("admin")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /admin/bookings/{booking_id}/admin-close

    Resolves an overdue booking by marking it 'admin_closed'.

    **What this does:**
    - Sets booking_state.status = 'admin_closed'
    - Writes a BOOKING_ADMIN_CLOSED audit event with actor, timestamp,
      original_status, and optional closure_note

    **What this does NOT do:**
    - Does NOT set checked_out_at (no fake checkout timestamp)
    - Does NOT emit BOOKING_CHECKED_OUT
    - Does NOT trigger settlement or financial records
    - Does NOT create or cancel cleaning/checkout tasks
    - Does NOT affect LINE notifications

    **Eligibility:**
    Booking must have status 'active' or 'confirmed', check_out < today,
    and checked_out_at IS NULL. Already-resolved or checked-out bookings
    are rejected.

    **Body (optional JSON):**
    - closure_note (str): Optional admin note explaining the closure.
    """
    if body is None:
        body = {}

    closure_note = str(body.get("closure_note", "")).strip() or None

    try:
        db = client if client is not None else _get_supabase_client()

        # 1. Fetch the booking
        result = (
            db.table("booking_state")
            .select("booking_id, status, check_out, checked_out_at, tenant_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return err(
                "BOOKING_NOT_FOUND",
                "Booking not found for this tenant",
                status=404,
                booking_id=booking_id,
            )

        row = result.data[0]
        current_status = (row.get("status") or "").lower()
        check_out = row.get("check_out")       # YYYY-MM-DD string or None
        checked_out_at = row.get("checked_out_at")

        # 2. Eligibility validation
        if current_status == "admin_closed":
            return err(
                "ALREADY_CLOSED",
                "Booking is already admin_closed",
                status=400,
                booking_id=booking_id,
            )

        if current_status == "checked_out" or checked_out_at:
            return err(
                "ALREADY_CHECKED_OUT",
                "Booking already has a checkout record — admin close not applicable",
                status=400,
                booking_id=booking_id,
            )

        if current_status not in _ELIGIBLE_STATUSES:
            return err(
                "NOT_ELIGIBLE",
                f"Booking status '{current_status}' is not eligible for admin close "
                f"(must be active or confirmed with a past checkout date)",
                status=400,
                booking_id=booking_id,
            )

        if not check_out:
            return err(
                "MISSING_CHECKOUT_DATE",
                "Booking has no check_out date — cannot determine overdue state",
                status=400,
                booking_id=booking_id,
            )

        today_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        if check_out >= today_str:
            return err(
                "NOT_OVERDUE",
                f"Booking checkout date ({check_out}) has not yet passed — "
                "admin close is only for overdue bookings",
                status=400,
                booking_id=booking_id,
            )

        # 3. Apply admin_closed status
        closed_at = datetime.now(tz=timezone.utc).isoformat()

        update_result = (
            db.table("booking_state")
            .update({
                "status": "admin_closed",
                # Intentionally NOT setting checked_out_at —
                # this is not a checkout event, it is an admin closure.
            })
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )

        if not update_result.data:
            logger.error(
                "admin_close: update returned no data for booking=%s tenant=%s",
                booking_id, tenant_id,
            )
            return err("INTERNAL_ERROR", "Failed to update booking status", status=500)

        # 4. Write audit trail — this is the only event emitted
        audit_payload: dict = {
            "action":             "BOOKING_ADMIN_CLOSED",
            "original_status":    current_status,
            "original_check_out": check_out,
            "closed_at":          closed_at,
            # Explicit enumeration of what was NOT done
            "settlement_triggered": False,
            "tasks_affected":       False,
            "checkout_timestamp_set": False,
        }
        if closure_note:
            audit_payload["closure_note"] = closure_note

        write_audit_event(
            tenant_id=tenant_id,
            actor_id=tenant_id,
            action="BOOKING_ADMIN_CLOSED",
            entity_type="booking",
            entity_id=booking_id,
            payload=audit_payload,
            client=db,
        )

        logger.info(
            "admin_close: booking=%s closed by tenant=%s original_status=%s check_out=%s",
            booking_id, tenant_id, current_status, check_out,
        )

        return ok({
            "booking_id":      booking_id,
            "status":          "admin_closed",
            "original_status": current_status,
            "closed_at":       closed_at,
            "closure_note":    closure_note,
            # Explicit: what was NOT triggered
            "settlement_triggered":    False,
            "tasks_affected":          False,
            "checkout_timestamp_set":  False,
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /admin/bookings/%s/admin-close error tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return err("INTERNAL_ERROR", "An unexpected internal error occurred", status=500)
