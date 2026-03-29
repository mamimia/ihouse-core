"""
Phase 998 — Early Check-out Approval Router
============================================

This router manages the operational early check-out workflow.
It is NOT responsible for OTA-side repricing, night-cost refunds,
or any commercial channel-side adjustment. Scope: operational
approval + internal settlement setup only.

Endpoints:

    POST /admin/bookings/{booking_id}/early-checkout/request
         Record guest's early departure request (ops staff intake).
         Allowed: admin, ops, manager.

    POST /admin/bookings/{booking_id}/early-checkout/approve
         Grant early checkout approval + reschedule task.
         Allowed: admin only, OR manager with can_approve_early_checkout permission.
         This is the ONLY endpoint that sets early_checkout_approved = true.

    DELETE /admin/bookings/{booking_id}/early-checkout/approve
         Revoke approval (only if checkout has not yet occurred).
         Allowed: admin, OR approving manager.

    GET /admin/bookings/{booking_id}/early-checkout
         Full early checkout state for this booking.
         Allowed: admin, manager, ops.

Invariants:
    - booking_state.check_out (original OTA date) is NEVER overwritten.
    - early_checkout_date is the ONLY field that holds the effective early date.
    - Approval requires early_checkout_date to be set and in the future (or today).
    - A checkout worker cannot call these endpoints. They only respond to the flag.
    - All mutations write to admin_audit_log.
    - Task rescheduling on approval: due_date → early_checkout_date, priority → HIGH,
      is_early_checkout = true, original_due_date = prior due_date.
    - Revocation only allowed if booking is still checked_in (not checked_out).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, date as date_type
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["early-checkout"])

# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------

# Roles allowed to record an intake request
_INTAKE_ROLES = frozenset({"admin", "ops", "manager"})

# Roles that may call the approve endpoint (before capability check)
_APPROVE_BASE_ROLES = frozenset({"admin", "manager"})

# Valid request source values
_VALID_REQUEST_SOURCES = frozenset({
    "phone", "message", "guest_portal", "ops_escalation", "other"
})


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _audit(db: Any, tenant_id: str, actor_id: str, action: str,
           entity_id: str, details: dict) -> None:
    try:
        db.table("admin_audit_log").insert({
            "tenant_id":    tenant_id,
            "actor_id":     actor_id,
            "action":       action,
            "entity_type":  "booking",
            "entity_id":    entity_id,
            "details":      details,
            "performed_at": _now_iso(),
        }).execute()
    except Exception as exc:
        logger.warning("early_checkout: audit write failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Permission helper — can this identity approve early checkout?
# ---------------------------------------------------------------------------

def _can_approve(db: Any, tenant_id: str, identity: dict) -> bool:
    """
    Phase 998: Only admin and explicitly-granted operational managers may approve.

    Admin: always yes.
    Manager: only if tenant_permissions.permissions contains
             {"can_approve_early_checkout": true} for this user.

    ops, worker, checkout: never.
    """
    role = identity.get("role", "")
    if role == "admin":
        return True
    if role == "manager":
        user_id = identity.get("user_id", "")
        try:
            res = (
                db.table("tenant_permissions")
                .select("permissions")
                .eq("user_id", user_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if rows:
                perms = rows[0].get("permissions") or {}
                return bool(perms.get("can_approve_early_checkout", False))
        except Exception as exc:
            logger.warning("early_checkout: permission lookup failed for user=%s: %s", user_id, exc)
    return False


# ---------------------------------------------------------------------------
# Booking state helpers
# ---------------------------------------------------------------------------

def _get_booking(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("booking_state")
            .select(
                "booking_id, tenant_id, status, check_in, check_out, guest_name, property_id, "
                "early_checkout_approved, early_checkout_approved_by, early_checkout_approved_at, "
                "early_checkout_reason, early_checkout_date, early_checkout_time, "
                "early_checkout_requested_at, early_checkout_request_source, "
                "early_checkout_request_note, early_checkout_approval_note, "
                "checked_out_at"
            )
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _reschedule_checkout_task(
    db: Any, tenant_id: str, booking_id: str, early_date: str
) -> dict:
    """
    On approval: reschedule the CHECKOUT_VERIFY task to the early checkout date.
    Snapshots original due_date, sets is_early_checkout=true, bumps priority to HIGH.
    Returns {"updated": bool, "task_id": str | None}.
    """
    try:
        # Find active CHECKOUT_VERIFY task for this booking
        res = (
            db.table("tasks")
            .select("task_id, due_date, priority, status")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("kind", "CHECKOUT_VERIFY")
            .not_.in_("status", ["COMPLETED", "CANCELED"])
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"updated": False, "task_id": None, "reason": "no_active_task"}

        task = rows[0]
        task_id = task["task_id"]
        original_due = task["due_date"]

        db.table("tasks").update({
            "due_date":         early_date,
            "is_early_checkout": True,
            "original_due_date": original_due,
            "priority":         "HIGH",   # time-sensitive early departure
            "urgency":          "urgent",
            "updated_at":       _now_iso(),
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        return {"updated": True, "task_id": task_id, "original_due_date": original_due}

    except Exception as exc:
        logger.warning("early_checkout: task reschedule failed for booking=%s: %s", booking_id, exc)
        return {"updated": False, "task_id": None, "reason": str(exc)}


def _revert_checkout_task(
    db: Any, tenant_id: str, booking_id: str
) -> dict:
    """
    On revocation: restore original due_date, clear is_early_checkout, reset priority.
    """
    try:
        res = (
            db.table("tasks")
            .select("task_id, original_due_date, priority")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("kind", "CHECKOUT_VERIFY")
            .eq("is_early_checkout", True)
            .not_.in_("status", ["COMPLETED", "CANCELED"])
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"reverted": False, "reason": "no_early_checkout_task"}

        task = rows[0]
        task_id = task["task_id"]
        restore_date = task.get("original_due_date")

        update = {
            "is_early_checkout":  False,
            "priority":           "MEDIUM",
            "urgency":            "normal",
            "updated_at":         _now_iso(),
        }
        if restore_date:
            update["due_date"] = restore_date
            update["original_due_date"] = None

        db.table("tasks").update(update).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()
        return {"reverted": True, "task_id": task_id, "restored_due_date": restore_date}

    except Exception as exc:
        logger.warning("early_checkout: task revert failed for booking=%s: %s", booking_id, exc)
        return {"reverted": False, "reason": str(exc)}


# ===========================================================================
# Phase 998 — POST /admin/bookings/{booking_id}/early-checkout/request
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/early-checkout/request",
    summary="Record guest early departure request intake (Phase 998)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def record_early_checkout_request(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Record that a guest has requested early departure.

    This captures the intake event without granting approval.
    Use /approve to actually unlock early checkout operations.

    Required body fields:
        request_source: 'phone' | 'message' | 'guest_portal' | 'ops_escalation' | 'other'

    Optional:
        request_note: free text from intake staff
        early_checkout_date: proposed YYYY-MM-DD (may be confirmed at approval)
        early_checkout_time: proposed HH:MM

    Allowed roles: admin, ops, manager.
    """
    role = identity.get("role", "")
    if role not in _INTAKE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot record early checkout requests."},
        )
    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    request_source = (body.get("request_source") or "").strip()
    if request_source not in _VALID_REQUEST_SOURCES:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={
                "detail": f"request_source must be one of: {sorted(_VALID_REQUEST_SOURCES)}",
                "provided": request_source,
            },
        )

    try:
        db = client or _get_db()

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        current_status = (booking.get("status") or "").lower()
        if current_status not in ("checked_in", "active"):
            return make_error_response(
                status_code=409, code="INVALID_STATE",
                extra={
                    "detail": f"Cannot record early checkout request for booking with status '{current_status}'. "
                              "Booking must be checked_in.",
                    "current_status": current_status,
                },
            )

        now = _now_iso()
        update = {
            "early_checkout_requested_at":   now,
            "early_checkout_request_source": request_source,
            "early_checkout_request_note":   body.get("request_note") or None,
            "updated_at_ms":                 int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        }

        # Optionally capture proposed early date (not binding until /approve)
        proposed_date = (body.get("early_checkout_date") or "").strip()[:10]
        if proposed_date:
            update["early_checkout_date"] = proposed_date
        proposed_time = (body.get("early_checkout_time") or "").strip()[:5]
        if proposed_time:
            update["early_checkout_time"] = proposed_time

        db.table("booking_state").update(update).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        _audit(db, tenant_id, actor_id, "early_checkout.request_received", booking_id, {
            "request_source":      request_source,
            "request_note":        body.get("request_note"),
            "proposed_early_date": proposed_date or None,
            "original_checkout":   str(booking.get("check_out", "")),
            "recorded_by":         actor_id,
        })

        return JSONResponse(status_code=200, content={
            "status":          "request_recorded",
            "booking_id":      booking_id,
            "request_source":  request_source,
            "proposed_date":   proposed_date or None,
            "recorded_by":     actor_id,
            "recorded_at":     now,
        })

    except Exception as exc:
        logger.exception("early_checkout.request booking=%s tenant=%s: %s", booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 998 — POST /admin/bookings/{booking_id}/early-checkout/approve
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/early-checkout/approve",
    summary="Approve guest early departure + reschedule task (Phase 998)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_early_checkout(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Grant early checkout approval for this booking.

    Sets early_checkout_approved = true, records effective early checkout date,
    and reschedules the CHECKOUT_VERIFY task to the approved date.

    After this call, the checkout worker can execute checkout before check_out date.

    Required body fields:
        early_checkout_date: YYYY-MM-DD — the approved effective departure date

    Optional:
        early_checkout_time: HH:MM
        reason: guest's reason for early departure
        approval_note: manager's operational note

    Permission: admin always. Manager only with can_approve_early_checkout = true
                in tenant_permissions.permissions.

    A checkout worker CANNOT call this endpoint.
    """
    role = identity.get("role", "")
    if role not in _APPROVE_BASE_ROLES:
        return make_error_response(
            status_code=403, code="APPROVAL_FORBIDDEN",
            extra={
                "detail": "Early checkout approval requires Admin or an Operational Manager "
                          "with explicit approval permission.",
                "role": role,
            },
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        # Fine-grained capability check (manager requires grant)
        if not _can_approve(db, tenant_id, identity):
            return make_error_response(
                status_code=403, code="APPROVAL_FORBIDDEN",
                extra={
                    "detail": "Your manager account does not have the 'can_approve_early_checkout' permission. "
                              "Contact your admin to grant this capability.",
                },
            )

        # Validate required fields
        early_date = (body.get("early_checkout_date") or "").strip()[:10]
        if not early_date or len(early_date) != 10:
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "early_checkout_date (YYYY-MM-DD) is required."},
            )

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        current_status = (booking.get("status") or "").lower()
        if current_status not in ("checked_in", "active"):
            return make_error_response(
                status_code=409, code="INVALID_STATE",
                extra={
                    "detail": f"Cannot approve early checkout for booking with status '{current_status}'. "
                              "Booking must be checked_in.",
                    "current_status": current_status,
                },
            )

        # Guard: early_checkout_date must not be after the original check_out
        original_checkout = str(booking.get("check_out") or "")[:10]
        if original_checkout and early_date >= original_checkout:
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={
                    "detail": f"early_checkout_date ({early_date}) must be before the original checkout date "
                              f"({original_checkout}). Use the normal checkout flow for same-day or later checkouts.",
                    "early_checkout_date": early_date,
                    "original_checkout_date": original_checkout,
                },
            )

        # Guard: early_checkout_date must be today or in the future
        today_str = date_type.today().isoformat()
        if early_date < today_str:
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={
                    "detail": f"early_checkout_date ({early_date}) cannot be in the past. "
                              f"Today is {today_str}.",
                    "early_checkout_date": early_date,
                    "today": today_str,
                },
            )

        # Already approved? Idempotent re-approval is allowed (updates the date)
        already_approved = booking.get("early_checkout_approved", False)

        now = _now_iso()
        update = {
            "early_checkout_approved":      True,
            "early_checkout_approved_by":   actor_id,
            "early_checkout_approved_at":   now,
            "early_checkout_date":          early_date,
            "early_checkout_reason":        body.get("reason") or booking.get("early_checkout_reason"),
            "early_checkout_approval_note": body.get("approval_note") or None,
            "updated_at_ms":                int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        }
        early_time = (body.get("early_checkout_time") or "").strip()[:5]
        if early_time:
            update["early_checkout_time"] = early_time

        db.table("booking_state").update(update).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Reschedule the CHECKOUT_VERIFY task
        task_result = _reschedule_checkout_task(db, tenant_id, booking_id, early_date)

        _audit(db, tenant_id, actor_id, "early_checkout.approved", booking_id, {
            "approved_by":              actor_id,
            "effective_checkout_date":  early_date,
            "effective_checkout_time":  early_time or None,
            "original_checkout_date":   original_checkout,
            "reason":                   body.get("reason"),
            "approval_note":            body.get("approval_note"),
            "task_rescheduled":         task_result.get("updated", False),
            "task_id":                  task_result.get("task_id"),
            "was_already_approved":     already_approved,
        })

        return JSONResponse(status_code=200, content={
            "status":                   "approved",
            "booking_id":               booking_id,
            "early_checkout_date":      early_date,
            "early_checkout_time":      early_time or None,
            "original_checkout_date":   original_checkout,
            "approved_by":              actor_id,
            "approved_at":              now,
            "reason":                   body.get("reason"),
            "approval_note":            body.get("approval_note"),
            "task_reschedule":          task_result,
        })

    except Exception as exc:
        logger.exception("early_checkout.approve booking=%s tenant=%s: %s", booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 998 — DELETE /admin/bookings/{booking_id}/early-checkout/approve
# ===========================================================================

@router.delete(
    "/admin/bookings/{booking_id}/early-checkout/approve",
    summary="Revoke early checkout approval (Phase 998)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def revoke_early_checkout(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Revoke early checkout approval.

    Only allowed if the booking has not yet been checked out.
    Restores the task to its original due_date and resets priority.

    Allowed: admin only, OR manager with can_approve_early_checkout.
    """
    role = identity.get("role", "")
    if role not in _APPROVE_BASE_ROLES:
        return make_error_response(
            status_code=403, code="APPROVAL_FORBIDDEN",
            extra={"detail": "Revoking early checkout requires Admin or an approved Operational Manager."},
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        if not _can_approve(db, tenant_id, identity):
            return make_error_response(
                status_code=403, code="APPROVAL_FORBIDDEN",
                extra={"detail": "Your account does not have the 'can_approve_early_checkout' permission."},
            )

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        if not booking.get("early_checkout_approved"):
            return make_error_response(
                status_code=409, code="NOT_APPROVED",
                extra={"detail": "This booking does not have an active early checkout approval."},
            )

        # Cannot revoke after checkout has occurred
        if booking.get("checked_out_at"):
            return make_error_response(
                status_code=409, code="ALREADY_CHECKED_OUT",
                extra={"detail": "Cannot revoke early checkout approval — booking has already been checked out."},
            )

        now = _now_iso()
        db.table("booking_state").update({
            "early_checkout_approved":      False,
            "early_checkout_approved_by":   None,
            "early_checkout_approved_at":   None,
            "early_checkout_date":          None,
            "early_checkout_time":          None,
            "early_checkout_approval_note": None,
            "updated_at_ms":                int(datetime.now(tz=timezone.utc).timestamp() * 1000),
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Revert task rescheduling
        task_result = _revert_checkout_task(db, tenant_id, booking_id)

        _audit(db, tenant_id, actor_id, "early_checkout.revoked", booking_id, {
            "revoked_by":               actor_id,
            "original_checkout_date":   str(booking.get("check_out", "")),
            "was_early_date":           str(booking.get("early_checkout_date", "")),
            "task_reverted":            task_result.get("reverted", False),
        })

        return JSONResponse(status_code=200, content={
            "status":       "revoked",
            "booking_id":   booking_id,
            "revoked_by":   actor_id,
            "revoked_at":   now,
            "task_revert":  task_result,
        })

    except Exception as exc:
        logger.exception("early_checkout.revoke booking=%s tenant=%s: %s", booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 998 — GET /admin/bookings/{booking_id}/early-checkout
# ===========================================================================

@router.get(
    "/admin/bookings/{booking_id}/early-checkout",
    summary="Get full early checkout state for a booking (Phase 998)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_early_checkout_state(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the complete early checkout state for a booking including:
    - Request intake details
    - Approval details
    - Current task state
    - Eligibility for approval

    Allowed: admin, manager, ops.
    """
    role = identity.get("role", "")
    if role not in (_INTAKE_ROLES | frozenset({"admin"})):
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot read early checkout state."},
        )

    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        # Get active task state
        task_data = None
        try:
            res = (
                db.table("tasks")
                .select("task_id, due_date, original_due_date, is_early_checkout, status, priority")
                .eq("tenant_id", tenant_id)
                .eq("booking_id", booking_id)
                .eq("kind", "CHECKOUT_VERIFY")
                .not_.in_("status", ["COMPLETED", "CANCELED"])
                .limit(1)
                .execute()
            )
            rows = res.data or []
            if rows:
                task_data = rows[0]
        except Exception:
            pass

        # Can caller approve? (informational for UI rendering)
        caller_can_approve = _can_approve(db, tenant_id, identity)

        return JSONResponse(status_code=200, content={
            "booking_id":              booking_id,
            "original_checkout_date":  str(booking.get("check_out") or ""),
            "booking_status":          booking.get("status"),

            # Request intake
            "request": {
                "recorded":  bool(booking.get("early_checkout_requested_at")),
                "source":    booking.get("early_checkout_request_source"),
                "note":      booking.get("early_checkout_request_note"),
                "at":        str(booking.get("early_checkout_requested_at") or ""),
                "proposed_date": str(booking.get("early_checkout_date") or "")
                                 if not booking.get("early_checkout_approved") else None,
            },

            # Approval
            "approval": {
                "approved":            bool(booking.get("early_checkout_approved")),
                "approved_by":         booking.get("early_checkout_approved_by"),
                "approved_at":         str(booking.get("early_checkout_approved_at") or ""),
                "effective_date":      str(booking.get("early_checkout_date") or ""),
                "effective_time":      booking.get("early_checkout_time"),
                "reason":              booking.get("early_checkout_reason"),
                "approval_note":       booking.get("early_checkout_approval_note"),
            },

            # Task impact
            "task": task_data,

            # Caller context
            "caller_can_approve": caller_can_approve,
        })

    except Exception as exc:
        logger.exception("early_checkout.get booking=%s tenant=%s: %s", booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
