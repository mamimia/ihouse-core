"""
Phase 1012 — Self Check-in Admin Router (Framework Generalization)
==================================================================

Admin/OM control surface for the Self Check-in umbrella.

Property modes (from properties.self_checkin_config.mode):
  'default'   — property operates in self check-in mode for all bookings.
                The pre_arrival_scanner auto-approves. Admin uses this router
                for overrides, monitoring, resend, and staffed override.
  'late_only' — staffed check-in by default. Admin/Manager explicitly approves
                self check-in for a specific booking (Late Self Check-in).
  'disabled'  — no self check-in. These endpoints will reject Late actions.

Endpoints:

    POST /admin/bookings/{booking_id}/self-checkin/request
         Late mode only: record that a booking needs self check-in.
         Moves self_checkin_status: none → requested.
         Allowed: admin, ops, manager.
         Blocked if property mode is 'disabled'.

    POST /admin/bookings/{booking_id}/self-checkin/approve
         Approve self check-in + issue token + send portal link.
         Also used by pre_arrival_scanner (system-approved, Late mode path for admin).
         Allowed: admin always, OR manager with can_approve_self_checkin.
         Blocked if property mode is 'disabled'.

    DELETE /admin/bookings/{booking_id}/self-checkin/approve
         Revoke approval (only before access_released).
         For Default mode: also sets self_checkin_staff_override=true.
         Revokes the SELF_CHECKIN access token.

    GET /admin/bookings/{booking_id}/self-checkin
         Full self check-in state for this booking.
         Allowed: admin, manager, ops.

    POST /admin/bookings/{booking_id}/self-checkin/resend
         Re-send portal link (issues fresh token).
         Allowed: admin, manager.

    POST /admin/bookings/{booking_id}/self-checkin/staffed-override
         Override a Default-mode booking back to staffed check-in.
         Suppresses future auto-portal issuance for this booking.
         Allowed: admin, manager.

Invariants:
    - INV-DISABLED-01: mode='disabled' blocks all Late actions. Hard stop.
    - INV-ACCESS-BOUNDARY: Access code never returned in admin responses.
    - INV-AUDIT-01: All mutations write to admin_audit_log.
    - Revocation only allowed before access_released.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["self-checkin"])


# ---------------------------------------------------------------------------
# Role constants
# ---------------------------------------------------------------------------

_INTAKE_ROLES = frozenset({"admin", "ops", "manager"})
_APPROVE_BASE_ROLES = frozenset({"admin", "manager"})
_READ_ROLES = frozenset({"admin", "ops", "manager"})

# Valid self_checkin_status values (matches DB CHECK constraint)
_VALID_STATUSES = frozenset({
    "none", "requested", "approved", "in_progress",
    "access_released", "completed", "followup_required",
})


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client
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
    """Best-effort audit event to admin_audit_log."""
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
        logger.warning("self_checkin: audit write failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Permission helper
# ---------------------------------------------------------------------------

def _can_approve(db: Any, tenant_id: str, identity: dict) -> bool:
    """
    Phase 1005: Only admin and explicitly-granted managers may approve.

    Admin: always yes.
    Manager: only if tenant_permissions.permissions has
             {"can_approve_self_checkin": true} for this user.
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
                return bool(perms.get("can_approve_self_checkin", False))
        except Exception as exc:
            logger.warning("self_checkin: permission lookup failed for user=%s: %s", user_id, exc)
    return False


# ---------------------------------------------------------------------------
# Booking state helpers
# ---------------------------------------------------------------------------

_BOOKING_SELECT = (
    "booking_id, tenant_id, status, property_id, check_in, check_out, guest_name, "
    "self_checkin_status, self_checkin_approved, self_checkin_approved_by, "
    "self_checkin_approved_at, self_checkin_reason, self_checkin_requested_at, "
    "self_checkin_requested_by, self_checkin_portal_sent_at, "
    "self_checkin_access_released_at, self_checkin_completed_at, "
    "self_checkin_token_hash, self_checkin_steps_completed, self_checkin_config"
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


def _get_property_self_checkin_config(db: Any, tenant_id: str, property_id: str) -> dict:
    """Return the self_checkin_config for a property, with defaults."""
    defaults = {
        # Mode (Phase 1012 umbrella model)
        "mode": "disabled",
        # Gate 1 — Pre-access steps (block access code until complete)
        "pre_access_steps": ["id_photo", "agreement"],
        # Gate 2 — Post-entry steps (tracked non-blocking, generate follow-up if incomplete)
        "post_entry_steps": [],
        # Legacy fields (Phase 1004 compat — used as fallback in service layer)
        "require_id_photo": True,
        "require_selfie": False,
        "require_agreement": True,
        "require_deposit_confirmation": False,
        # Timing
        "access_release_window_minutes": 0,
        "max_token_ttl_hours": 24,
        "portal_send_days_before": 2,
        "auto_send_portal_link": True,
        # Follow-up
        "followup_if_incomplete": True,
        # Content
        "custom_agreement_text": "",
        "step_instructions": {},
        "arrival_guide": {
            "entry_instructions": "",
            "on_arrival_what_to_do": "",
            "electricity_instructions": "",
            "key_locations": "",
            "emergency_contact": "",
        },
    }
    try:
        res = (
            db.table("properties")
            .select("self_checkin_config")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows:
            cfg = rows[0].get("self_checkin_config") or {}
            if isinstance(cfg, dict):
                return {**defaults, **cfg}
    except Exception:
        pass
    return defaults


# ---------------------------------------------------------------------------
# Token issuance helper
# ---------------------------------------------------------------------------

_PORTAL_BASE = os.environ.get("SELF_CHECKIN_PORTAL_URL", "https://app.domaniqo.com/self-checkin")
_DEFAULT_TOKEN_TTL_HOURS = 24


def _issue_self_checkin_token(
    db: Any,
    tenant_id: str,
    booking_id: str,
    guest_email: str = "",
    ttl_hours: int = _DEFAULT_TOKEN_TTL_HOURS,
) -> tuple[str, str, int]:
    """
    Issue a SELF_CHECKIN access token and record it.

    Returns (portal_url, token_hash, exp).
    """
    from services.access_token_service import (
        TokenType, issue_access_token, record_token,
    )
    import hashlib

    raw_token, exp = issue_access_token(
        token_type=TokenType.SELF_CHECKIN,
        entity_id=booking_id,
        email=guest_email,
        ttl_seconds=ttl_hours * 3600,
    )

    record_token(
        tenant_id=tenant_id,
        token_type=TokenType.SELF_CHECKIN,
        entity_id=booking_id,
        raw_token=raw_token,
        exp=exp,
        email=guest_email,
        metadata={"booking_id": booking_id, "flow": "self_checkin"},
        db=db,
    )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    portal_url = f"{_PORTAL_BASE}/{raw_token}"

    return portal_url, token_hash, exp


def _revoke_self_checkin_token(db: Any, tenant_id: str, token_hash: str) -> bool:
    """Revoke the SELF_CHECKIN token by hash."""
    from services.access_token_service import revoke_token
    return revoke_token(token_hash=token_hash, tenant_id=tenant_id, db=db)


# ---------------------------------------------------------------------------
# Notification dispatch helper
# ---------------------------------------------------------------------------

def _get_self_checkin_mode(config: dict) -> str:
    """Return the self_checkin_mode from a property config."""
    return config.get("mode") or "disabled"


def _assert_mode_allows_late(
    config: dict,
    booking_id: str,
) -> Optional[JSONResponse]:
    """
    INV-DISABLED-01: If property mode is 'disabled', block Late Self Check-in actions.
    Returns None if allowed, or an error JSONResponse if blocked.
    """
    mode = _get_self_checkin_mode(config)
    if mode == "disabled":
        return make_error_response(
            status_code=403, code="SELF_CHECKIN_DISABLED",
            extra={
                "detail": (
                    "Self check-in is disabled for this property. "
                    "Change the property's check-in mode to allow self check-in."
                ),
                "mode": mode,
                "booking_id": booking_id,
            },
        )
    return None


def _dispatch_portal_link(
    db: Any,
    tenant_id: str,
    portal_url: str,
    guest_name: str,
    property_name: str,
    mode: str = "late_only",
    to_phone: str | None = None,
    to_email: str | None = None,
) -> list[dict]:
    """Send portal link via SMS and/or email. Mode-aware message templates. Best-effort."""
    results = []

    # Mode-aware message framing
    if mode == "default":
        sms_body = (
            f"Hi {guest_name}, your self check-in for {property_name} is ready. "
            f"Complete your arrival steps here: {portal_url}"
        )
        email_subject = f"Your Self Check-in is Ready – {property_name}"
        email_body = (
            f"<p>Hi {guest_name},</p>"
            f"<p>Your arrival at <strong>{property_name}</strong> is almost here!</p>"
            f"<p>Complete your self check-in steps using the link below, and your access "
            f"details will be ready for you at check-in time:</p>"
            f'<p><a href="{portal_url}">{portal_url}</a></p>'
            f"<p>We look forward to your stay!</p>"
        )
    else:
        # Late mode framing
        sms_body = (
            f"Hi {guest_name}, your self check-in at {property_name} has been approved. "
            f"Complete your arrival here: {portal_url}"
        )
        email_subject = f"Self Check-in Approved – {property_name}"
        email_body = (
            f"<p>Hi {guest_name},</p>"
            f"<p>Your self check-in at <strong>{property_name}</strong> has been approved.</p>"
            f"<p>Please complete your check-in steps using the link below:</p>"
            f'<p><a href="{portal_url}">{portal_url}</a></p>'
            f"<p>Your access details will be available from the official check-in time.</p>"
            f"<p>Thank you!</p>"
        )

    if to_phone:
        try:
            from services.notification_dispatcher import dispatch_sms
            result = dispatch_sms(
                db=db,
                tenant_id=tenant_id,
                to_number=to_phone,
                body=sms_body,
                notification_type="self_checkin_portal",
                reference_id=None,
            )
            results.append(result)
        except Exception as exc:
            logger.warning("self_checkin: SMS dispatch failed: %s", exc)
            results.append({"channel": "sms", "status": "failed", "error": str(exc)})

    if to_email:
        try:
            from services.notification_dispatcher import dispatch_email
            result = dispatch_email(
                db=db,
                tenant_id=tenant_id,
                to_email=to_email,
                subject=email_subject,
                body_html=email_body,
                notification_type="self_checkin_portal",
                reference_id=None,
            )
            results.append(result)
        except Exception as exc:
            logger.warning("self_checkin: email dispatch failed: %s", exc)
            results.append({"channel": "email", "status": "failed", "error": str(exc)})

    return results


# ===========================================================================
# POST /admin/bookings/{booking_id}/self-checkin/request
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/self-checkin/request",
    summary="Record self check-in request (Phase 1005)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def record_self_checkin_request(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Record that a booking needs late self check-in.

    This is the intake step — captures the request without approval.
    Call /approve to issue the portal link.

    Moves self_checkin_status: none → requested.

    Optional body fields:
        reason: Why self check-in is needed (e.g. "guest arriving at 11 PM, no staff")
        guest_phone: Guest phone number for portal link delivery
        guest_email: Guest email for portal link delivery

    Allowed roles: admin, ops, manager.
    """
    role = identity.get("role", "")
    if role not in _INTAKE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot record self check-in requests."},
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        property_id = booking.get("property_id", "")
        prop_config = _get_property_self_checkin_config(db, tenant_id, property_id)

        # INV-DISABLED-01: Gate on property mode
        mode_err = _assert_mode_allows_late(prop_config, booking_id)
        if mode_err:
            return mode_err

        # /request is only meaningful for Late mode (late_only properties)
        # Default-mode properties are auto-approved by the scanner; /approve can be called directly.
        mode = _get_self_checkin_mode(prop_config)
        if mode == "default":
            return make_error_response(
                status_code=409, code="DEFAULT_MODE_NO_REQUEST",
                extra={
                    "detail": (
                        "This property operates in Default Self Check-in mode. "
                        "Portal links are issued automatically. Use /approve to issue manually."
                    ),
                    "mode": mode,
                },
            )

        # Must be an active/upcoming booking
        bk_status = (booking.get("status") or "").lower()
        if bk_status not in ("active", "confirmed", "observed"):
            return make_error_response(
                status_code=409, code="INVALID_STATE",
                extra={
                    "detail": f"Cannot request self check-in for booking with status '{bk_status}'. "
                              "Booking must be active, confirmed, or observed.",
                    "current_status": bk_status,
                },
            )

        # Idempotent: if already requested or further, just return current state
        sc_status = booking.get("self_checkin_status") or "none"
        if sc_status != "none":
            return JSONResponse(status_code=200, content={
                "status": "already_requested",
                "self_checkin_status": sc_status,
                "booking_id": booking_id,
                "noop": True,
            })

        now = _now_iso()
        update: dict = {
            "self_checkin_status": "requested",
            "self_checkin_requested_at": now,
            "self_checkin_requested_by": actor_id,
            "self_checkin_reason": body.get("reason") or None,
            "updated_at_ms": _now_ms(),
        }

        db.table("booking_state").update(update).eq(
            "booking_id", booking_id
        ).eq("tenant_id", tenant_id).execute()

        _audit(db, tenant_id, actor_id, "self_checkin.request_recorded", booking_id, {
            "reason": body.get("reason"),
            "guest_phone": body.get("guest_phone"),
            "guest_email": body.get("guest_email"),
            "recorded_by": actor_id,
        })

        return JSONResponse(status_code=200, content={
            "status": "request_recorded",
            "self_checkin_status": "requested",
            "booking_id": booking_id,
            "recorded_by": actor_id,
            "recorded_at": now,
        })

    except Exception as exc:
        logger.exception("self_checkin.request booking=%s: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# POST /admin/bookings/{booking_id}/self-checkin/approve
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/self-checkin/approve",
    summary="Approve self check-in + send portal link (Phase 1005)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def approve_self_checkin(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Approve late self check-in for this booking.

    This is the binding action:
      - Issues a SELF_CHECKIN access token
      - Sends the portal link via SMS/email (if provided)
      - Sets self_checkin_approved = true
      - Moves self_checkin_status → 'approved'

    At least one of guest_phone or guest_email should be provided
    for delivery (warning if neither).

    Required body fields: (none, but recommended):
        guest_phone: E.164 phone number for SMS delivery
        guest_email: Email for link delivery
        guest_name: Guest name for personalization

    Optional:
        reason: Override/set the reason for self check-in
        token_ttl_hours: Override token TTL (default from property config)

    Permission model:
        admin: always allowed.
        manager: only if can_approve_self_checkin=true in tenant_permissions.
    """
    role = identity.get("role", "")
    if role not in _APPROVE_BASE_ROLES:
        return make_error_response(
            status_code=403, code="APPROVAL_FORBIDDEN",
            extra={
                "detail": "Self check-in approval requires Admin or an "
                          "Operational Manager with explicit permission.",
                "role": role,
            },
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        if not _can_approve(db, tenant_id, identity):
            return make_error_response(
                status_code=403, code="APPROVAL_FORBIDDEN",
                extra={
                    "detail": "Your account does not have the 'can_approve_self_checkin' permission. "
                              "Contact your admin.",
                },
            )

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        bk_status = (booking.get("status") or "").lower()
        if bk_status not in ("active", "confirmed", "observed"):
            return make_error_response(
                status_code=409, code="INVALID_STATE",
                extra={
                    "detail": f"Cannot approve self check-in for booking with status '{bk_status}'.",
                    "current_status": bk_status,
                },
            )

        sc_status = booking.get("self_checkin_status") or "none"
        if sc_status in ("access_released", "completed", "followup_required"):
            return make_error_response(
                status_code=409, code="INVALID_STATE",
                extra={
                    "detail": f"Self check-in is already in '{sc_status}' state.",
                    "self_checkin_status": sc_status,
                },
            )

        property_id = booking.get("property_id", "")

        # Get property config for TTL and requirements
        prop_config = _get_property_self_checkin_config(db, tenant_id, property_id)
        ttl_hours = body.get("token_ttl_hours") or prop_config.get("max_token_ttl_hours", _DEFAULT_TOKEN_TTL_HOURS)

        # Resolve guest contact info
        guest_phone = (body.get("guest_phone") or "").strip() or None
        guest_email = (body.get("guest_email") or "").strip() or None
        guest_name = (body.get("guest_name") or booking.get("guest_name") or "Guest").strip()

        # Issue token
        portal_url, token_hash, exp = _issue_self_checkin_token(
            db=db,
            tenant_id=tenant_id,
            booking_id=booking_id,
            guest_email=guest_email or "",
            ttl_hours=int(ttl_hours),
        )

        now = _now_iso()
        update: dict = {
            "self_checkin_status": "approved",
            "self_checkin_approved": True,
            "self_checkin_approved_by": actor_id,
            "self_checkin_approved_at": now,
            "self_checkin_token_hash": token_hash,
            "self_checkin_portal_sent_at": now,
            "self_checkin_config": prop_config,
            "updated_at_ms": _now_ms(),
        }
        if body.get("reason"):
            update["self_checkin_reason"] = body["reason"]

        db.table("booking_state").update(update).eq(
            "booking_id", booking_id
        ).eq("tenant_id", tenant_id).execute()

        # Phase 1014 — Late Mode CHECKIN_PREP Reframe
        # For late_only properties: find the existing CHECKIN_PREP task and re-frame it
        # so the worker knows the guest will self-check-in. We do NOT cancel it —
        # the worker must remain aware and available for post-entry follow-up.
        # Only re-frame PENDING tasks. ACKNOWLEDGED/IN_PROGRESS = worker already engaged.
        sc_mode = _get_self_checkin_mode(prop_config)
        if sc_mode == "late_only":
            try:
                task_res = (
                    db.table("tasks")
                    .select("task_id, status, description, metadata")
                    .eq("booking_id", booking_id)
                    .eq("tenant_id", tenant_id)
                    .eq("kind", "CHECKIN_PREP")
                    .eq("status", "PENDING")
                    .limit(1)
                    .execute()
                )
                if task_res.data:
                    task = task_res.data[0]
                    task_id = task["task_id"]
                    existing_meta = task.get("metadata") or {}
                    db.table("tasks").update({
                        "description": (
                            "⚠️ Guest will self-check-in — no physical arrival expected.\n\n"
                            "The guest has been approved for self check-in and will access "
                            "the property independently at or after the official check-in time.\n\n"
                            "Your role: Monitor for post-entry follow-up tasks. "
                            "If the guest misses required post-entry steps, a follow-up task will "
                            "be created automatically. Be reachable if the guest needs assistance."
                        ),
                        "metadata": {
                            **existing_meta,
                            "self_checkin_exception": True,
                            "self_checkin_approved_at": now,
                            "self_checkin_approved_by": actor_id,
                        },
                        "updated_at": now,
                    }).eq("task_id", task_id).eq("tenant_id", tenant_id).execute()
                    logger.info(
                        "self_checkin: reframed CHECKIN_PREP task=%s for booking=%s",
                        task_id, booking_id,
                    )
            except Exception as exc:
                logger.warning(
                    "self_checkin: CHECKIN_PREP reframe failed for booking=%s (non-blocking): %s",
                    booking_id, exc,
                )

        # Dispatch portal link (best-effort)
        notifications = []
        if guest_phone or guest_email:
            # Resolve property name for notification
            prop_name = property_id
            try:
                prop_res = (
                    db.table("properties")
                    .select("display_name, name")
                    .eq("property_id", property_id)
                    .limit(1)
                    .execute()
                )
                if prop_res.data:
                    prop_name = (
                        prop_res.data[0].get("display_name")
                        or prop_res.data[0].get("name")
                        or property_id
                    )
            except Exception:
                pass

            notifications = _dispatch_portal_link(
                db=db,
                tenant_id=tenant_id,
                portal_url=portal_url,
                guest_name=guest_name,
                property_name=prop_name,
                to_phone=guest_phone,
                to_email=guest_email,
            )

        _audit(db, tenant_id, actor_id, "self_checkin.approved", booking_id, {
            "approved_by": actor_id,
            "property_id": property_id,
            "guest_phone": guest_phone,
            "guest_email": guest_email,
            "token_ttl_hours": ttl_hours,
            "notifications_sent": len(notifications),
            "reason": body.get("reason") or booking.get("self_checkin_reason"),
        })

        logger.info(
            "self_checkin: approved booking=%s tenant=%s by=%s notify=%d",
            booking_id, tenant_id, actor_id, len(notifications),
        )

        return JSONResponse(status_code=200, content={
            "status": "approved",
            "self_checkin_status": "approved",
            "booking_id": booking_id,
            "property_id": property_id,
            "portal_url": portal_url,
            "approved_by": actor_id,
            "approved_at": now,
            "notifications": notifications,
            "no_recipient_warning": (
                "No guest_phone or guest_email provided. Portal link was not sent."
                if not guest_phone and not guest_email else None
            ),
        })

    except Exception as exc:
        logger.exception("self_checkin.approve booking=%s: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# DELETE /admin/bookings/{booking_id}/self-checkin/approve
# ===========================================================================

@router.delete(
    "/admin/bookings/{booking_id}/self-checkin/approve",
    summary="Revoke self check-in approval (Phase 1005)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def revoke_self_checkin(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Revoke an outstanding self check-in approval.

    Only allowed before access_released (once the guest has the code, it's too late).
    Revokes the token so the portal link becomes invalid.

    Permission: admin always. Manager with can_approve_self_checkin only.
    """
    role = identity.get("role", "")
    if role not in _APPROVE_BASE_ROLES:
        return make_error_response(
            status_code=403, code="APPROVAL_FORBIDDEN",
            extra={"detail": "Revoking self check-in requires Admin or authorized Manager."},
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        if not _can_approve(db, tenant_id, identity):
            return make_error_response(
                status_code=403, code="APPROVAL_FORBIDDEN",
                extra={"detail": "Your account does not have the 'can_approve_self_checkin' permission."},
            )

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        sc_status = booking.get("self_checkin_status") or "none"

        if sc_status == "none":
            return make_error_response(
                status_code=409, code="NOT_APPROVED",
                extra={"detail": "This booking does not have an active self check-in approval."},
            )

        if sc_status in ("access_released", "completed", "followup_required"):
            return make_error_response(
                status_code=409, code="ALREADY_RELEASED",
                extra={
                    "detail": "Cannot revoke self check-in — access has already been released to the guest.",
                    "self_checkin_status": sc_status,
                },
            )

        # Revoke the token
        token_hash = booking.get("self_checkin_token_hash")
        if token_hash:
            _revoke_self_checkin_token(db, tenant_id, token_hash)

        now = _now_iso()
        db.table("booking_state").update({
            "self_checkin_status": "none",
            "self_checkin_approved": False,
            "self_checkin_approved_by": None,
            "self_checkin_approved_at": None,
            "self_checkin_token_hash": None,
            "self_checkin_portal_sent_at": None,
            "self_checkin_steps_completed": {},
            "self_checkin_config": {},
            "updated_at_ms": _now_ms(),
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        _audit(db, tenant_id, actor_id, "self_checkin.revoked", booking_id, {
            "revoked_by": actor_id,
            "previous_status": sc_status,
            "token_revoked": bool(token_hash),
        })

        return JSONResponse(status_code=200, content={
            "status": "revoked",
            "self_checkin_status": "none",
            "booking_id": booking_id,
            "revoked_by": actor_id,
            "revoked_at": now,
        })

    except Exception as exc:
        logger.exception("self_checkin.revoke booking=%s: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# GET /admin/bookings/{booking_id}/self-checkin
# ===========================================================================

@router.get(
    "/admin/bookings/{booking_id}/self-checkin",
    summary="Get full self check-in state (Phase 1005)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_self_checkin_state(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Full self check-in state for a booking.

    Returns:
      - self_checkin_status (none|requested|approved|in_progress|access_released|completed|followup_required)
      - Approval details
      - Portal link delivery status
      - Guest step completion progress
      - Property self check-in config (required steps)
      - caller_can_approve

    Allowed: admin, manager, ops.
    """
    role = identity.get("role", "")
    if role not in _READ_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot read self check-in state."},
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

        sc_status = booking.get("self_checkin_status") or "none"
        steps = booking.get("self_checkin_steps_completed") or {}
        config = booking.get("self_checkin_config") or {}

        # Get property config for required steps
        property_id = booking.get("property_id", "")
        prop_config = _get_property_self_checkin_config(db, tenant_id, property_id)

        # Build required vs completed steps
        required_steps = []
        if prop_config.get("require_id_photo"):
            required_steps.append("id_photo")
        if prop_config.get("require_selfie"):
            required_steps.append("selfie")
        if prop_config.get("require_agreement"):
            required_steps.append("agreement")
        if prop_config.get("require_deposit_confirmation"):
            required_steps.append("deposit")

        completed_steps = [s for s in required_steps if steps.get(s)]
        pending_steps = [s for s in required_steps if not steps.get(s)]

        # Follow-up task (if any)
        followup_task = None
        if sc_status == "followup_required":
            try:
                task_res = (
                    db.table("tasks")
                    .select("task_id, status, priority, assigned_to, due_date")
                    .eq("tenant_id", tenant_id)
                    .eq("booking_id", booking_id)
                    .eq("kind", "SELF_CHECKIN_FOLLOWUP")
                    .not_.in_("status", ["CANCELED"])
                    .limit(1)
                    .execute()
                )
                rows = task_res.data or []
                if rows:
                    followup_task = rows[0]
            except Exception:
                pass

        caller_can_approve = _can_approve(db, tenant_id, identity)

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "property_id": property_id,
            "booking_status": booking.get("status"),
            "self_checkin_status": sc_status,

            "request": {
                "recorded": sc_status != "none",
                "reason": booking.get("self_checkin_reason"),
                "requested_at": str(booking.get("self_checkin_requested_at") or ""),
                "requested_by": booking.get("self_checkin_requested_by"),
            },

            "approval": {
                "approved": bool(booking.get("self_checkin_approved")),
                "approved_by": booking.get("self_checkin_approved_by"),
                "approved_at": str(booking.get("self_checkin_approved_at") or ""),
                "portal_sent_at": str(booking.get("self_checkin_portal_sent_at") or ""),
            },

            "progress": {
                "required_steps": required_steps,
                "completed_steps": completed_steps,
                "pending_steps": pending_steps,
                "steps_detail": steps,
                "completion_pct": (
                    round(len(completed_steps) / len(required_steps) * 100)
                    if required_steps else 100
                ),
            },

            "access": {
                "released": sc_status in ("access_released", "completed", "followup_required"),
                "released_at": str(booking.get("self_checkin_access_released_at") or ""),
                "completed_at": str(booking.get("self_checkin_completed_at") or ""),
            },

            "followup_task": followup_task,
            "property_config": prop_config,
            "caller_can_approve": caller_can_approve,
        })

    except Exception as exc:
        logger.exception("self_checkin.get booking=%s: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# POST /admin/bookings/{booking_id}/self-checkin/resend
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/self-checkin/resend",
    summary="Re-send self check-in portal link (Phase 1005)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def resend_self_checkin_link(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Re-send the self check-in portal link.

    Issues a fresh token (the old one remains valid until expiry).
    Requires the booking to have self_checkin_status in approved or in_progress.

    Body:
        guest_phone: E.164 phone number
        guest_email: email address
        guest_name: for personalization

    At least one of guest_phone or guest_email required.
    Allowed: admin, manager.
    """
    role = identity.get("role", "")
    if role not in _APPROVE_BASE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot resend self check-in links."},
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")

    guest_phone = (body.get("guest_phone") or "").strip() or None
    guest_email = (body.get("guest_email") or "").strip() or None

    if not guest_phone and not guest_email:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "At least one of guest_phone or guest_email is required."},
        )

    try:
        db = client or _get_db()

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        sc_status = booking.get("self_checkin_status") or "none"
        if sc_status not in ("approved", "in_progress"):
            return make_error_response(
                status_code=409, code="INVALID_STATE",
                extra={
                    "detail": f"Cannot resend link — self check-in status is '{sc_status}'. "
                              "Must be approved or in_progress.",
                },
            )

        property_id = booking.get("property_id", "")
        guest_name = (body.get("guest_name") or booking.get("guest_name") or "Guest").strip()

        # Issue fresh token
        prop_config = _get_property_self_checkin_config(db, tenant_id, property_id)
        ttl_hours = prop_config.get("max_token_ttl_hours", _DEFAULT_TOKEN_TTL_HOURS)

        portal_url, token_hash, _ = _issue_self_checkin_token(
            db=db,
            tenant_id=tenant_id,
            booking_id=booking_id,
            guest_email=guest_email or "",
            ttl_hours=int(ttl_hours),
        )

        # Update booking_state with new token hash
        now = _now_iso()
        db.table("booking_state").update({
            "self_checkin_token_hash": token_hash,
            "self_checkin_portal_sent_at": now,
            "updated_at_ms": _now_ms(),
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        # Resolve property name
        prop_name = property_id
        try:
            prop_res = (
                db.table("properties")
                .select("display_name, name")
                .eq("property_id", property_id)
                .limit(1)
                .execute()
            )
            if prop_res.data:
                prop_name = (
                    prop_res.data[0].get("display_name")
                    or prop_res.data[0].get("name")
                    or property_id
                )
        except Exception:
            pass

        notifications = _dispatch_portal_link(
            db=db, tenant_id=tenant_id, portal_url=portal_url,
            guest_name=guest_name, property_name=prop_name,
            to_phone=guest_phone, to_email=guest_email,
        )

        _audit(db, tenant_id, actor_id, "self_checkin.link_resent", booking_id, {
            "resent_by": actor_id,
            "guest_phone": guest_phone,
            "guest_email": guest_email,
            "notifications_sent": len(notifications),
        })

        return JSONResponse(status_code=200, content={
            "status": "link_resent",
            "booking_id": booking_id,
            "portal_url": portal_url,
            "notifications": notifications,
            "resent_by": actor_id,
            "resent_at": now,
        })

    except Exception as exc:
        logger.exception("self_checkin.resend booking=%s: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# POST /admin/bookings/{booking_id}/self-checkin/staffed-override
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/self-checkin/staffed-override",
    summary="Override a Default-mode booking to staffed check-in (Phase 1012)",
    status_code=200,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def staffed_override(
    booking_id: str,
    body: dict = {},
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Override a self check-in booking back to staffed physical check-in.

    Use cases:
    - VIP arrival requiring personal hospitality
    - Sensitive guest (ID issue, owner request)
    - Operational concern discovered before check-in
    - Manual override by management

    Effect:
    - Sets booking_state.self_checkin_staff_override = true
    - Sets booking_state.self_checkin_override_reason = body.reason
    - Resets self_checkin_status → 'none' if in (requested, approved, in_progress)
    - Revokes existing SELF_CHECKIN token if one was issued
    - Does NOT affect access_released / completed / followup_required states
      (if guest already has access, override is a no-op on the access itself)
    - Marks booking so pre_arrival_scanner will NOT re-issue portal link

    When override is set, the booking follows the staffed check-in path.
    Normal CHECKIN_PREP task assignment and worker flow applies.

    Allowed roles: admin, manager.
    """
    role = identity.get("role", "")
    if role not in {"admin", "manager"}:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only admins and managers can apply staffed override."},
        )

    tenant_id = identity["tenant_id"]
    actor_id = identity.get("user_id", "unknown")
    reason = (body.get("reason") or "").strip()[:500]

    if not reason:
        return make_error_response(
            status_code=400, code="VALIDATION_ERROR",
            extra={"detail": "A reason is required for staffed override."},
        )

    try:
        db = client or _get_db()

        booking = _get_booking(db, tenant_id, booking_id)
        if not booking:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        sc_status = booking.get("self_checkin_status") or "none"

        # If access already released, cannot undo the access — warn admin
        if sc_status in ("access_released", "completed", "followup_required"):
            return make_error_response(
                status_code=409, code="ACCESS_ALREADY_RELEASED",
                extra={
                    "detail": (
                        "Guest has already been granted access. "
                        "The staffed override can only be applied before access is released."
                    ),
                    "self_checkin_status": sc_status,
                },
            )

        now = _now_iso()

        # Revoke existing token if there is one
        token_hash = booking.get("self_checkin_token_hash")
        if token_hash:
            try:
                _revoke_self_checkin_token(db, tenant_id, token_hash)
            except Exception as exc:
                logger.warning("staffed_override: token revoke failed: %s", exc)

        update: dict = {
            "self_checkin_staff_override": True,
            "self_checkin_override_reason": reason,
            "self_checkin_override_at": now,
            "self_checkin_override_by": actor_id,
            "updated_at_ms": _now_ms(),
        }

        # Reset self_checkin_status if it was in a pre-access state
        if sc_status in ("none", "requested", "approved", "in_progress"):
            update["self_checkin_status"] = "none"
            update["self_checkin_approved"] = False

        db.table("booking_state").update(update).eq(
            "booking_id", booking_id,
        ).eq("tenant_id", tenant_id).execute()

        _audit(db, tenant_id, actor_id, "self_checkin.staffed_override", booking_id, {
            "reason": reason,
            "previous_status": sc_status,
            "override_at": now,
        })

        logger.info(
            "self_checkin.staffed_override booking=%s by=%s reason=%r",
            booking_id, actor_id, reason,
        )

        return JSONResponse(status_code=200, content={
            "status": "staffed_override_applied",
            "booking_id": booking_id,
            "self_checkin_staff_override": True,
            "self_checkin_status": "none",
            "override_reason": reason,
            "override_by": actor_id,
            "override_at": now,
            "message": (
                "This booking will proceed with staffed check-in. "
                "No self check-in portal link will be issued."
            ),
        })

    except Exception as exc:
        logger.exception("self_checkin.staffed_override booking=%s: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
