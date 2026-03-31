"""
Phase 998 / 998b — Early Check-out Approval Router
====================================================

This router manages the operational early check-out workflow.
It is NOT responsible for OTA-side repricing, night-cost refunds,
or any commercial channel-side adjustment. Scope: operational
approval + internal settlement setup only.

Endpoints:

    POST /admin/bookings/{booking_id}/early-checkout/request
         Record guest's early departure request (ops staff intake).
         Moves early_checkout_status: none → requested.
         Allowed: admin, ops, manager.

    POST /admin/bookings/{booking_id}/early-checkout/approve
         Grant early checkout approval + reschedule task.
         Moves early_checkout_status: requested|none → approved.
         Allowed: admin always, OR manager with can_approve_early_checkout
         in tenant_permissions.permissions.
         This is the ONLY call that sets early_checkout_approved = true
         and makes the checkout task actionable early.

    DELETE /admin/bookings/{booking_id}/early-checkout/approve
         Revoke approval (only if checkout has not yet occurred).
         Moves early_checkout_status: approved → requested|none.
         Allowed: admin, OR approving manager with capability.

    GET /admin/bookings/{booking_id}/early-checkout
         Full early checkout state for this booking.
         Allowed: admin, manager, ops.

Invariants (Phase 998b):
    - booking_state.check_out (original OTA date) is NEVER overwritten.
    - early_checkout_effective_at (TIMESTAMPTZ) is the authoritative approved
      effective departure moment. Replaces weak separate date+time text fields.
    - early_checkout_date (DATE) is kept alongside for fast date-only eligibility
      comparisons and task due_date updates.
    - early_checkout_status tracks the lifecycle explicitly:
        none → requested → approved → completed
      rather than inferring state from scattered boolean flags.
    - A checkout worker cannot call these endpoints.
    - All mutations write to admin_audit_log.
    - Task rescheduling on approval: due_date → early_checkout_date (DATE),
      is_early_checkout=true, original_due_date=prior due_date, priority→HIGH.
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

# Roles that may call the approve/revoke endpoints (then fine-grained capability check)
_APPROVE_BASE_ROLES = frozenset({"admin", "manager"})

# Valid request source values
_VALID_REQUEST_SOURCES = frozenset({
    "phone", "message", "guest_portal", "ops_escalation", "other"
})

# Valid early_checkout_status values
_EARLY_CHECKOUT_STATUSES = frozenset({"none", "requested", "approved", "completed"})


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


def _now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


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
# Permission helper
# ---------------------------------------------------------------------------

def _can_approve(db: Any, tenant_id: str, identity: dict) -> bool:
    """
    Phase 998: Only admin and explicitly-granted operational managers may approve.

    Admin: always yes.
    Manager: only if tenant_permissions.permissions has
             {"can_approve_early_checkout": true} for this user.

    This is the delegation model:
      Admin = always authorized.
      Operational Manager = authorized ONLY when Admin has delegated via permissions.
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

_BOOKING_SELECT = (
    "booking_id, tenant_id, status, check_in, check_out, guest_name, property_id, "
    "early_checkout_approved, early_checkout_approved_by, early_checkout_approved_at, "
    "early_checkout_reason, early_checkout_date, early_checkout_effective_at, "
    "early_checkout_status, "
    "early_checkout_requested_at, early_checkout_request_source, "
    "early_checkout_request_note, early_checkout_approval_note, "
    "checked_out_at"
)


def _get_booking(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("booking_state")
            .select(_BOOKING_SELECT)
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _build_effective_at(date_str: str, time_str: Optional[str]) -> Optional[str]:
    """
    Build a proper ISO 8601 UTC timestamp from a YYYY-MM-DD date and optional HH:MM time.
    If no time is given, defaults to 11:00 local naive (represented as UTC for storage;
    UI layer can adjust for property timezone in the future).
    Returns None if date_str is invalid.
    """
    try:
        date_str = date_str.strip()[:10]
        time_part = (time_str or "11:00").strip()[:5]
        # Validate format
        dt = datetime.strptime(f"{date_str}T{time_part}", "%Y-%m-%dT%H:%M")
        # Store as UTC (timezone-naive input treated as local operational time;
        # stored with +00:00 suffix — property timezone support is a future phase)
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except (ValueError, TypeError):
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
            "due_date":          early_date,
            "is_early_checkout": True,
            "original_due_date": original_due,
            "priority":          "HIGH",
            "urgency":           "urgent",
            "updated_at":        _now_iso(),
        }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        return {"updated": True, "task_id": task_id, "original_due_date": original_due}

    except Exception as exc:
        logger.warning("early_checkout: task reschedule failed booking=%s: %s", booking_id, exc)
        return {"updated": False, "task_id": None, "reason": str(exc)}


def _reschedule_cleaning_task(
    db: Any, tenant_id: str, booking_id: str, early_date: str
) -> dict:
    """
    Phase 1028 — On early checkout approval: reschedule the CLEANING task to match.

    Canonical invariant: CLEANING always follows CHECKOUT on the same day.
    When a checkout is moved earlier, the cleaning must also move to that same day.
    Without this, the cleaner is still scheduled for the original checkout date
    while the property needs cleaning on the new (earlier) date.

    Finds the CLEANING task for this booking (must be non-terminal).
    Snapshots original due_date in original_due_date for revocation support.
    Sets is_early_checkout=true, bumps priority to HIGH.
    """
    try:
        res = (
            db.table("tasks")
            .select("task_id, due_date, status")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("kind", "CLEANING")
            .not_.in_("status", ["COMPLETED", "CANCELED"])
            # Prefer the checkout-oriented CLEANING (due on check_out date, not check_in)
            # Both are acceptable to reschedule — take the one with the latest due_date
            # since the checkout CLEANING should be on/after check_in CLEANING.
            .order("due_date", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"updated": False, "task_id": None, "reason": "no_active_cleaning_task"}

        task = rows[0]
        task_id = task["task_id"]
        original_due = task["due_date"]

        update_payload = {
            "due_date":          early_date,
            "is_early_checkout": True,
            "original_due_date": original_due,
            "priority":          "HIGH",
            "urgency":           "urgent",
            "updated_at":        _now_iso(),
        }

        # Phase 1030-guard: If the CLEANING task has no assigned worker (was created
        # without a Primary cleaner), try to heal the assignment now using the
        # current Primary cleaner for this property. Early checkout is a critical
        # operational trigger — if someone is moving the date, they need a cleaner.
        if not task.get("assigned_to"):
            try:
                prop_res = (
                    db.table("tasks")
                    .select("property_id, tenant_id")
                    .eq("task_id", task_id)
                    .limit(1)
                    .execute()
                )
                prop_row = (prop_res.data or [{}])[0]
                _prop_id = prop_row.get("property_id")
                _tenant_id = prop_row.get("tenant_id")
                if _prop_id and _tenant_id:
                    assign_res = (
                        db.table("staff_property_assignments")
                        .select("user_id")
                        .eq("tenant_id", _tenant_id)
                        .eq("property_id", _prop_id)
                        .order("priority", desc=False)
                        .limit(10)
                        .execute()
                    )
                    candidate_ids = [r["user_id"] for r in (assign_res.data or [])]
                    if candidate_ids:
                        roles_res = (
                            db.table("tenant_permissions")
                            .select("user_id, worker_roles")
                            .eq("tenant_id", _tenant_id)
                            .in_("user_id", candidate_ids)
                            .execute()
                        )
                        for r in (roles_res.data or []):
                            if "cleaner" in (r.get("worker_roles") or []):
                                update_payload["assigned_to"] = r["user_id"]
                                logger.info(
                                    "early_checkout: healed unassigned CLEANING task=%s → assigned to cleaner=%s",
                                    task_id, r["user_id"],
                                )
                                break
            except Exception as _heal_exc:
                logger.warning("early_checkout: failed to heal unassigned CLEANING task=%s: %s", task_id, _heal_exc)

        db.table("tasks").update(update_payload).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()

        logger.info(
            "early_checkout: CLEANING task rescheduled booking=%s task=%s %s→%s",
            booking_id, task_id, original_due, early_date,
        )
        return {"updated": True, "task_id": task_id, "original_due_date": original_due}

    except Exception as exc:
        logger.warning("early_checkout: CLEANING reschedule failed booking=%s: %s", booking_id, exc)
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
        logger.warning("early_checkout: task revert failed booking=%s: %s", booking_id, exc)
        return {"reverted": False, "reason": str(exc)}


def _revert_cleaning_task(
    db: Any, tenant_id: str, booking_id: str
) -> dict:
    """
    Phase 1028 — On revocation: restore the CLEANING task to its original due_date.
    Mirrors _revert_checkout_task for CLEANING kind.
    """
    try:
        res = (
            db.table("tasks")
            .select("task_id, original_due_date")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("kind", "CLEANING")
            .eq("is_early_checkout", True)
            .not_.in_("status", ["COMPLETED", "CANCELED"])
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return {"reverted": False, "reason": "no_early_cleaning_task"}

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
        logger.warning("early_checkout: CLEANING revert failed booking=%s: %s", booking_id, exc)
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

    This is the intake step only — it captures the request without approval.
    The checkout task remains locked. Call /approve to unlock it.

    Moves early_checkout_status: none → requested.

    Required body fields:
        request_source: 'phone' | 'message' | 'guest_portal' | 'ops_escalation' | 'other'

    Optional:
        request_note: free text from intake staff
        proposed_date: proposed YYYY-MM-DD (informational, not binding)
        proposed_time: proposed HH:MM (informational, not binding)

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
                    "detail": f"Cannot record early checkout request for booking with "
                              f"status '{current_status}'. Booking must be checked_in.",
                    "current_status": current_status,
                },
            )

        now = _now_iso()
        update: dict = {
            "early_checkout_requested_at":   now,
            "early_checkout_request_source": request_source,
            "early_checkout_request_note":   body.get("request_note") or None,
            "early_checkout_status":         "requested",
            "updated_at_ms":                 _now_ms(),
        }

        # Store proposed timing (informational — becomes binding at /approve)
        proposed_date = (body.get("proposed_date") or "").strip()[:10]
        proposed_time = (body.get("proposed_time") or "").strip()[:5]
        if proposed_date:
            update["early_checkout_date"] = proposed_date
        # Build effective_at only if we have a proposed date (non-binding preview)
        proposed_effective_at = _build_effective_at(proposed_date, proposed_time or None) if proposed_date else None
        if proposed_effective_at:
            update["early_checkout_effective_at"] = proposed_effective_at

        db.table("booking_state").update(update).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        _audit(db, tenant_id, actor_id, "early_checkout.request_received", booking_id, {
            "request_source":        request_source,
            "request_note":          body.get("request_note"),
            "proposed_date":         proposed_date or None,
            "proposed_effective_at": proposed_effective_at,
            "original_checkout":     str(booking.get("check_out", "")),
            "recorded_by":           actor_id,
        })

        return JSONResponse(status_code=200, content={
            "status":                "request_recorded",
            "early_checkout_status": "requested",
            "booking_id":            booking_id,
            "request_source":        request_source,
            "proposed_date":         proposed_date or None,
            "proposed_effective_at": proposed_effective_at,
            "recorded_by":           actor_id,
            "recorded_at":           now,
        })

    except Exception as exc:
        logger.exception("early_checkout.request booking=%s tenant=%s: %s", booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 998 — POST /admin/bookings/{booking_id}/early-checkout/approve
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/early-checkout/approve",
    summary="Approve early departure + reschedule checkout task (Phase 998)",
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

    This is the binding action:
      - Sets early_checkout_approved = true
      - Sets early_checkout_effective_at (proper TIMESTAMPTZ — date + time)
      - Sets early_checkout_date (DATE convenience field for eligibility checks)
      - Moves early_checkout_status → 'approved'
      - Reschedules the CHECKOUT_VERIFY task to the approved effective date

    After this call, the checkout worker can execute checkout before check_out date.
    The checkout task becomes an Early Check-out task (is_early_checkout=true, due_date updated).

    Required body fields:
        early_checkout_date: YYYY-MM-DD — the approved effective departure date

    Optional:
        early_checkout_time: HH:MM — specific departure time (defaults to 11:00 if omitted)
        reason: guest's reason (flight change, emergency, etc.)
        approval_note: manager's operational note (internal, e.g. "notify cleaning team")

    Permission model:
        admin: always allowed.
        manager: only if can_approve_early_checkout=true in tenant_permissions.permissions.
                 This is an explicit delegation from admin — not a default manager right.
        ops/worker: never.
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

        # Fine-grained: manager must have capability grant
        if not _can_approve(db, tenant_id, identity):
            return make_error_response(
                status_code=403, code="APPROVAL_FORBIDDEN",
                extra={
                    "detail": "Your manager account does not have the 'can_approve_early_checkout' permission. "
                              "Contact your admin to grant this capability.",
                },
            )

        # Require early_checkout_date
        early_date = (body.get("early_checkout_date") or "").strip()[:10]
        if not early_date or len(early_date) != 10:
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "early_checkout_date (YYYY-MM-DD) is required."},
            )

        # Optional time component — stored as proper TIMESTAMPTZ
        early_time = (body.get("early_checkout_time") or "").strip()[:5] or None
        effective_at = _build_effective_at(early_date, early_time)
        if not effective_at:
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Invalid early_checkout_date format: '{early_date}'."},
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

        # Guard: early_checkout_date must be strictly before original check_out
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

        # Guard: early_checkout_date must be today or future
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

        already_approved = booking.get("early_checkout_approved", False)

        now = _now_iso()
        update: dict = {
            "early_checkout_approved":      True,
            "early_checkout_approved_by":   actor_id,
            "early_checkout_approved_at":   now,
            "early_checkout_date":          early_date,          # DATE for eligibility checks
            "early_checkout_effective_at":  effective_at,        # TIMESTAMPTZ — authoritative
            "early_checkout_status":        "approved",
            "early_checkout_reason":        body.get("reason") or booking.get("early_checkout_reason"),
            "early_checkout_approval_note": body.get("approval_note") or None,
            "updated_at_ms":                _now_ms(),
        }

        db.table("booking_state").update(update).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Reschedule CHECKOUT_VERIFY task to early_date
        task_result = _reschedule_checkout_task(db, tenant_id, booking_id, early_date)

        # Phase 1028 — also reschedule CLEANING to the same early date.
        # Canonical rule: CLEANING always follows CHECKOUT on the same day.
        # If the checkout is moved earlier, the cleaner must also be notified.
        cleaning_result = _reschedule_cleaning_task(db, tenant_id, booking_id, early_date)

        _audit(db, tenant_id, actor_id, "early_checkout.approved", booking_id, {
            "approved_by":              actor_id,
            "effective_checkout_date":  early_date,
            "effective_at":             effective_at,
            "original_checkout_date":   original_checkout,
            "reason":                   body.get("reason"),
            "approval_note":            body.get("approval_note"),
            "checkout_task_rescheduled":task_result.get("updated", False),
            "checkout_task_id":         task_result.get("task_id"),
            "cleaning_task_rescheduled":cleaning_result.get("updated", False),
            "cleaning_task_id":         cleaning_result.get("task_id"),
            "was_already_approved":     already_approved,
        })

        return JSONResponse(status_code=200, content={
            "status":                      "approved",
            "early_checkout_status":       "approved",
            "booking_id":                  booking_id,
            "early_checkout_date":         early_date,
            "early_checkout_effective_at": effective_at,
            "original_checkout_date":      original_checkout,
            "approved_by":                 actor_id,
            "approved_at":                 now,
            "reason":                      body.get("reason"),
            "approval_note":               body.get("approval_note"),
            "task_reschedule":             task_result,
            "cleaning_reschedule":         cleaning_result,
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
    Revoke an outstanding early checkout approval.

    Only allowed if the booking has not yet been checked out.
    Restores the task to its original due_date and resets priority.
    Moves early_checkout_status: approved → requested (if request was recorded)
    or none (if approval was granted without a request intake step).

    Permission: admin always. Manager with can_approve_early_checkout only.
    """
    role = identity.get("role", "")
    if role not in _APPROVE_BASE_ROLES:
        return make_error_response(
            status_code=403, code="APPROVAL_FORBIDDEN",
            extra={"detail": "Revoking early checkout requires Admin or an authorized Operational Manager."},
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

        if booking.get("checked_out_at"):
            return make_error_response(
                status_code=409, code="ALREADY_CHECKED_OUT",
                extra={"detail": "Cannot revoke early checkout approval — booking has already been checked out."},
            )

        # Revert status to 'requested' if a request was recorded, else 'none'
        revert_status = (
            "requested" if booking.get("early_checkout_requested_at") else "none"
        )

        now = _now_iso()
        db.table("booking_state").update({
            "early_checkout_approved":      False,
            "early_checkout_approved_by":   None,
            "early_checkout_approved_at":   None,
            "early_checkout_date":          None,
            "early_checkout_effective_at":  None,
            "early_checkout_status":        revert_status,
            "early_checkout_approval_note": None,
            "updated_at_ms":                _now_ms(),
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        task_result = _revert_checkout_task(db, tenant_id, booking_id)
        # Phase 1028 — also revert CLEANING to original due_date on revocation
        cleaning_revert = _revert_cleaning_task(db, tenant_id, booking_id)

        _audit(db, tenant_id, actor_id, "early_checkout.revoked", booking_id, {
            "revoked_by":             actor_id,
            "original_checkout_date": str(booking.get("check_out", "")),
            "was_early_date":         str(booking.get("early_checkout_date", "")),
            "was_effective_at":       str(booking.get("early_checkout_effective_at", "")),
            "reverted_status":        revert_status,
            "checkout_task_reverted": task_result.get("reverted", False),
            "cleaning_task_reverted": cleaning_revert.get("reverted", False),
        })

        return JSONResponse(status_code=200, content={
            "status":                "revoked",
            "early_checkout_status": revert_status,
            "booking_id":            booking_id,
            "revoked_by":            actor_id,
            "revoked_at":            now,
            "task_revert":           task_result,
            "cleaning_revert":       cleaning_revert,
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
    Full early checkout state for a booking.

    Returns:
      - early_checkout_status (none|requested|approved|completed)
      - Original booking checkout date
      - Request intake details (source, note, timestamp)
      - Approval details (effective date, effective_at TIMESTAMPTZ, approved_by, reason)
      - Active CHECKOUT_VERIFY task state (rescheduled or normal)
      - caller_can_approve (whether the calling user can approve this)

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

        # Active CHECKOUT_VERIFY task state
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

        caller_can_approve = _can_approve(db, tenant_id, identity)

        ec_status = booking.get("early_checkout_status") or "none"

        return JSONResponse(status_code=200, content={
            "booking_id":             booking_id,
            "original_checkout_date": str(booking.get("check_out") or ""),
            "booking_status":         booking.get("status"),
            "early_checkout_status":  ec_status,   # none|requested|approved|completed

            # Request intake
            "request": {
                "recorded":       ec_status in ("requested", "approved", "completed"),
                "source":         booking.get("early_checkout_request_source"),
                "note":           booking.get("early_checkout_request_note"),
                "at":             str(booking.get("early_checkout_requested_at") or ""),
                # proposed_date is only meaningful before approval
                "proposed_date":  str(booking.get("early_checkout_date") or "")
                                  if ec_status == "requested" else None,
            },

            # Approval
            "approval": {
                "approved":            bool(booking.get("early_checkout_approved")),
                "approved_by":         booking.get("early_checkout_approved_by"),
                "approved_at":         str(booking.get("early_checkout_approved_at") or ""),
                # effective_at is the authoritative moment (date+time as TIMESTAMPTZ)
                "effective_at":        str(booking.get("early_checkout_effective_at") or ""),
                # effective_date is the date-only convenience field
                "effective_date":      str(booking.get("early_checkout_date") or ""),
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
