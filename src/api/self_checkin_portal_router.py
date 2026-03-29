"""
Phase 1012 — Guest Self Check-in Portal Router (Framework Generalization)
=========================================================================

Public (no JWT), token-gated guest-facing endpoints for self check-in.

The guest receives a URL like:
    https://app.domaniqo.com/self-checkin/{token}

Token verified via access_token_service (type SELF_CHECKIN).
No account required.

Two-Gate Architecture (Phase 1012):
  Gate 1 — Pre-Access: Steps that must be completed before access code is shown.
    Endpoints: /identity, /agreement, /deposit
    Trigger:   /complete — evaluates Gate 1 → on success, releases access
  Gate 2 — Post-Entry: Steps completed after entering the property. Non-blocking.
    Endpoint:  /post-entry/{step_key}
    Checked by: follow-up evaluator, creates SELF_CHECKIN_FOLLOWUP if incomplete

MODE-NEUTRAL: This router does not know whether the booking came from
Default or Late mode. Both use identical portal logic.

Invariants:
    - Token must be valid, non-expired, non-revoked, type SELF_CHECKIN
    - Booking must have self_checkin_status in ('approved', 'in_progress')
      for mutation endpoints (access_released/completed/followup_required for reads)
    - Access code is NEVER returned until all 6 Gate 1 conditions are met
    - ID photos are stored in the 'guest-identity' storage bucket
    - Each step is idempotent; re-submitting overwrites previous submission
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["self-checkin-portal"])


# ---------------------------------------------------------------------------
# DB helper
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


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

def _verify_self_checkin_token(token: str, db: Any = None) -> tuple[Optional[dict], Optional[str]]:
    """
    Verify a SELF_CHECKIN access token.
    Returns (claims_dict, None) on success, or (None, error_message) on failure.
    """
    from services.access_token_service import TokenType, verify_access_token

    result = verify_access_token(
        raw_token=token,
        expected_type=TokenType.SELF_CHECKIN,
        db=db,
    )

    if result.get("valid"):
        return result, None

    return None, result.get("error", "Token invalid or expired")


def _get_booking_for_portal(db: Any, booking_id: str) -> Optional[dict]:
    """Fetch booking_state for a self-check-in token's associated booking."""
    try:
        res = (
            db.table("booking_state")
            .select(
                "booking_id, tenant_id, status, property_id, check_in, check_out, "
                "guest_name, self_checkin_status, self_checkin_approved, "
                "self_checkin_steps_completed, self_checkin_config, "
                "self_checkin_access_released_at"
            )
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_property_for_portal(db: Any, property_id: str, tenant_id: str) -> Optional[dict]:
    """Fetch property info needed for the portal display."""
    try:
        res = (
            db.table("properties")
            .select(
                "property_id, display_name, name, address, city, country, "
                "checkin_time, checkout_time, "
                "house_rules, emergency_contact, "
                "access_code, door_code, wifi_name, wifi_password, "
                "self_checkin_config, "
                "deposit_required, deposit_amount, deposit_currency, deposit_method"
            )
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Shared: token validation + booking state check
# ---------------------------------------------------------------------------

def _validate_portal_request(
    token: str, db: Any
) -> tuple[Optional[dict], Optional[dict], Optional[JSONResponse]]:
    """
    Common validation for all portal endpoints.
    Returns (booking, claims, None) on success,
    or (None, None, error_response) on failure.
    """
    claims, err = _verify_self_checkin_token(token, db=db)
    if err:
        return None, None, make_error_response(
            status_code=401, code="TOKEN_INVALID",
            extra={"detail": err},
        )

    booking_id = claims.get("entity_id") or claims.get("booking_id")
    if not booking_id:
        return None, None, make_error_response(
            status_code=401, code="TOKEN_INVALID",
            extra={"detail": "Token does not reference a valid booking"},
        )

    booking = _get_booking_for_portal(db, booking_id)
    if not booking:
        return None, None, make_error_response(
            status_code=404, code=ErrorCode.NOT_FOUND,
            extra={"detail": "Booking not found"},
        )

    sc_status = booking.get("self_checkin_status") or "none"

    # Allow read-only access for terminal states
    if sc_status in ("access_released", "completed", "followup_required"):
        return booking, claims, None

    # Reject revoked or uninitiated states
    if sc_status not in ("approved", "in_progress"):
        return None, None, make_error_response(
            status_code=409, code="INVALID_STATE",
            extra={
                "detail": f"Self check-in is not available (status: {sc_status})",
                "self_checkin_status": sc_status,
            },
        )

    if not booking.get("self_checkin_approved"):
        return None, None, make_error_response(
            status_code=409, code="APPROVAL_REVOKED",
            extra={"detail": "Self check-in approval has been revoked"},
        )

    return booking, claims, None


def _build_step_status(config: dict, steps_completed: dict) -> dict:
    """
    Build structured step status for both gate layers.
    """
    from services.self_checkin_service import (
        resolve_pre_access_steps,
        resolve_post_entry_steps,
    )

    pre_required = resolve_pre_access_steps(config)
    post_required = resolve_post_entry_steps(config)

    step_instructions = config.get("step_instructions") or {}

    pre_steps = []
    for s in pre_required:
        pre_steps.append({
            "key": s,
            "completed": bool(steps_completed.get(s)),
            "detail": steps_completed.get(s),
            "instruction": step_instructions.get(s) or _default_instruction(s),
        })

    post_steps = []
    for s in post_required:
        post_steps.append({
            "key": s,
            "completed": bool(steps_completed.get(s)),
            "detail": steps_completed.get(s),
            "instruction": step_instructions.get(s) or _default_instruction(s),
        })

    pre_done = sum(1 for s in pre_steps if s["completed"])
    post_done = sum(1 for s in post_steps if s["completed"])

    return {
        "pre_access": {
            "steps": pre_steps,
            "completed_count": pre_done,
            "required_count": len(pre_steps),
            "all_complete": pre_done == len(pre_steps),
        },
        "post_entry": {
            "steps": post_steps,
            "completed_count": post_done,
            "required_count": len(post_steps),
            "all_complete": post_done == len(post_steps),
        },
    }


def _default_instruction(step_key: str) -> str:
    return {
        "id_photo": "Please take a clear photo of your passport or government-issued ID.",
        "selfie": "Please take a selfie for identity verification.",
        "agreement": "Please read and accept our house rules before entering.",
        "deposit": "Please acknowledge the security deposit requirement.",
        "electricity_meter": "Please record or photograph the electricity meter reading after entry.",
        "arrival_photos": "Please take arrival photos of the property condition after entry.",
    }.get(step_key, "Please complete this step.")


# ===========================================================================
# GET /self-checkin/{token}
# ===========================================================================

@router.get(
    "/self-checkin/{token}",
    summary="Load self check-in portal state (Phase 1012)",
    status_code=200,
)
async def get_portal_state(
    token: str,
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Load the full portal state for a self check-in session.

    Returns:
    - Booking summary (property name, dates, guest name)
    - Pre-access steps (must complete before access code is shown)
    - Post-entry steps (complete after entering, non-blocking)
    - Property arrival guide (rich instructional content)
    - Access credentials (ONLY after Gate 1 passes and time gate met)
    - Guest portal URL (available after check-in, for portal continuity)
    """
    db = client or _get_db()
    booking, claims, err_response = _validate_portal_request(token, db)
    if err_response:
        return err_response

    tenant_id = booking["tenant_id"]
    property_id = booking["property_id"]

    prop = _get_property_for_portal(db, property_id, tenant_id)

    # Merge config: booking snapshot takes precedence over property current config
    config = booking.get("self_checkin_config") or {}
    if not config and prop:
        prop_sc_config = prop.get("self_checkin_config") or {}
        config = prop_sc_config if isinstance(prop_sc_config, dict) else {}

    steps_completed = booking.get("self_checkin_steps_completed") or {}
    sc_status = booking.get("self_checkin_status") or "none"

    step_status = _build_step_status(config, steps_completed)

    # Arrival guide from property config
    prop_sc_config = (prop or {}).get("self_checkin_config") or {}
    if not isinstance(prop_sc_config, dict):
        prop_sc_config = {}
    arrival_guide = prop_sc_config.get("arrival_guide") or {}

    # Build property surface
    prop_surface = {
        "name": (prop or {}).get("display_name") or (prop or {}).get("name") or property_id,
        "address": (prop or {}).get("address"),
        "city": (prop or {}).get("city"),
        "country": (prop or {}).get("country"),
        "checkin_time": (prop or {}).get("checkin_time") or "15:00",
        "checkout_time": (prop or {}).get("checkout_time") or "11:00",
        "emergency_contact": (prop or {}).get("emergency_contact"),
        "arrival_guide": arrival_guide,
    }

    response: dict = {
        "booking": {
            "booking_id": booking["booking_id"],
            "guest_name": booking.get("guest_name", "Guest"),
            "check_in": str(booking.get("check_in", ""))[:10],
            "check_out": str(booking.get("check_out", ""))[:10],
        },
        "property": prop_surface,
        "self_checkin_status": sc_status,
        "steps": step_status,
    }

    # Additional step content for the UI
    if any(s["key"] == "agreement" for s in step_status["pre_access"]["steps"]):
        response["house_rules"] = (prop or {}).get("house_rules") or []
        response["custom_agreement_text"] = config.get("custom_agreement_text") or ""

    if any(s["key"] == "deposit" for s in step_status["pre_access"]["steps"]):
        response["deposit_info"] = {
            "required": (prop or {}).get("deposit_required", False),
            "amount": (prop or {}).get("deposit_amount"),
            "currency": (prop or {}).get("deposit_currency", "THB"),
            "method": (prop or {}).get("deposit_method"),
        }

    # Access credentials — only expose after Gate 1 AND time gate have passed
    if sc_status in ("access_released", "completed", "followup_required"):
        response["access"] = {
            "released": True,
            "released_at": str(booking.get("self_checkin_access_released_at") or ""),
            "access_code": (prop or {}).get("access_code") or (prop or {}).get("door_code"),
            "door_code": (prop or {}).get("door_code"),
            "wifi_name": (prop or {}).get("wifi_name"),
            "wifi_password": (prop or {}).get("wifi_password"),
        }
        # Portal continuity hint
        response["guest_portal_hint"] = (
            "Your check-in is complete. Access your full stay portal for house info, "
            "local recommendations, and assistance during your stay."
        )
    else:
        response["access"] = {"released": False}

    return JSONResponse(status_code=200, content=response)


# ===========================================================================
# POST /self-checkin/{token}/identity
# ===========================================================================

@router.post(
    "/self-checkin/{token}/identity",
    summary="Submit ID photo for self check-in (Phase 1012)",
    status_code=200,
)
async def submit_identity(
    token: str,
    id_photo: Optional[UploadFile] = File(None),
    selfie: Optional[UploadFile] = File(None),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Submit identity verification (Gate 1 step).
    Accepts id_photo and optional selfie. Both go to guest-identity storage bucket.
    Idempotent: re-submission overwrites.
    """
    db = client or _get_db()
    booking, claims, err_response = _validate_portal_request(token, db)
    if err_response:
        return err_response

    sc_status = booking.get("self_checkin_status") or "none"
    if sc_status in ("access_released", "completed", "followup_required"):
        return JSONResponse(status_code=200, content={"status": "already_completed", "noop": True})

    booking_id = booking["booking_id"]
    tenant_id = booking["tenant_id"]

    uploaded = {}

    if id_photo and id_photo.filename:
        try:
            content = await id_photo.read()
            ext = id_photo.filename.rsplit(".", 1)[-1] if "." in id_photo.filename else "jpg"
            path = f"{booking_id}/id_photo.{ext}"
            db.storage.from_("guest-identity").upload(
                path, content,
                file_options={"content-type": id_photo.content_type or "image/jpeg"},
            )
            uploaded["id_photo"] = path
        except Exception as exc:
            logger.warning("self_checkin: id_photo upload failed: %s", exc)
            uploaded["id_photo_error"] = str(exc)

    if selfie and selfie.filename:
        try:
            content = await selfie.read()
            ext = selfie.filename.rsplit(".", 1)[-1] if "." in selfie.filename else "jpg"
            path = f"{booking_id}/selfie.{ext}"
            db.storage.from_("guest-identity").upload(
                path, content,
                file_options={"content-type": selfie.content_type or "image/jpeg"},
            )
            uploaded["selfie"] = path
        except Exception as exc:
            logger.warning("self_checkin: selfie upload failed: %s", exc)
            uploaded["selfie_error"] = str(exc)

    steps = booking.get("self_checkin_steps_completed") or {}
    now = _now_iso()

    if "id_photo" in uploaded:
        steps["id_photo"] = {"completed_at": now, "storage_path": uploaded["id_photo"]}
    if "selfie" in uploaded:
        steps["selfie"] = {"completed_at": now, "storage_path": uploaded["selfie"]}

    update: dict = {"self_checkin_steps_completed": steps, "updated_at_ms": _now_ms()}
    if sc_status == "approved":
        update["self_checkin_status"] = "in_progress"

    db.table("booking_state").update(update).eq(
        "booking_id", booking_id,
    ).eq("tenant_id", tenant_id).execute()

    return JSONResponse(status_code=200, content={
        "status": "identity_submitted",
        "uploaded": uploaded,
        "steps_completed": list(steps.keys()),
    })


# ===========================================================================
# POST /self-checkin/{token}/agreement
# ===========================================================================

@router.post(
    "/self-checkin/{token}/agreement",
    summary="Accept house rules agreement (Phase 1012)",
    status_code=200,
)
async def submit_agreement(
    token: str,
    body: dict = {},
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Guest accepts the house rules / self check-in agreement (Gate 1 step).
    Body: { accepted: true, signature_name?: string }
    """
    db = client or _get_db()
    booking, claims, err_response = _validate_portal_request(token, db)
    if err_response:
        return err_response

    sc_status = booking.get("self_checkin_status") or "none"
    if sc_status in ("access_released", "completed", "followup_required"):
        return JSONResponse(status_code=200, content={"status": "already_completed", "noop": True})

    if not body.get("accepted"):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "You must accept the agreement (accepted: true)."},
        )

    booking_id = booking["booking_id"]
    tenant_id = booking["tenant_id"]

    steps = booking.get("self_checkin_steps_completed") or {}
    now = _now_iso()
    steps["agreement"] = {
        "completed_at": now,
        "accepted": True,
        "signature_name": body.get("signature_name") or None,
    }

    update: dict = {"self_checkin_steps_completed": steps, "updated_at_ms": _now_ms()}
    if sc_status == "approved":
        update["self_checkin_status"] = "in_progress"

    db.table("booking_state").update(update).eq(
        "booking_id", booking_id,
    ).eq("tenant_id", tenant_id).execute()

    return JSONResponse(status_code=200, content={
        "status": "agreement_accepted",
        "steps_completed": list(steps.keys()),
    })


# ===========================================================================
# POST /self-checkin/{token}/deposit
# ===========================================================================

@router.post(
    "/self-checkin/{token}/deposit",
    summary="Confirm deposit acknowledgement (Phase 1012)",
    status_code=200,
)
async def submit_deposit(
    token: str,
    body: dict = {},
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Guest acknowledges the security deposit requirement (Gate 1 step).
    This is acknowledgement only, not a payment.
    Body: { acknowledged: true }
    """
    db = client or _get_db()
    booking, claims, err_response = _validate_portal_request(token, db)
    if err_response:
        return err_response

    sc_status = booking.get("self_checkin_status") or "none"
    if sc_status in ("access_released", "completed", "followup_required"):
        return JSONResponse(status_code=200, content={"status": "already_completed", "noop": True})

    if not body.get("acknowledged"):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "You must acknowledge the deposit (acknowledged: true)."},
        )

    booking_id = booking["booking_id"]
    tenant_id = booking["tenant_id"]

    steps = booking.get("self_checkin_steps_completed") or {}
    now = _now_iso()
    steps["deposit"] = {"completed_at": now, "acknowledged": True}

    update: dict = {"self_checkin_steps_completed": steps, "updated_at_ms": _now_ms()}
    if sc_status == "approved":
        update["self_checkin_status"] = "in_progress"

    db.table("booking_state").update(update).eq(
        "booking_id", booking_id,
    ).eq("tenant_id", tenant_id).execute()

    return JSONResponse(status_code=200, content={
        "status": "deposit_acknowledged",
        "steps_completed": list(steps.keys()),
    })


# ===========================================================================
# POST /self-checkin/{token}/complete
# ===========================================================================

@router.post(
    "/self-checkin/{token}/complete",
    summary="Trigger Gate 1 access release evaluation (Phase 1012)",
    status_code=200,
)
async def complete_self_checkin(
    token: str,
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Guest triggers the Gate 1 evaluation. If all 6 conditions pass:
    - Booking → checked_in
    - Property → occupied
    - Access code + arrival guide returned in response
    - Post-entry steps checklist returned for what to do after entry
    - Guest HMAC token issued for Guest Portal continuity

    If Gate 1 fails, returns structured reason + friendly message.
    Guest can retry (most failures are time-based and self-resolving).
    """
    db = client or _get_db()
    booking, claims, err_response = _validate_portal_request(token, db)
    if err_response:
        return err_response

    sc_status = booking.get("self_checkin_status") or "none"

    # Already released — return existing access
    if sc_status in ("access_released", "completed", "followup_required"):
        prop = _get_property_for_portal(db, booking["property_id"], booking["tenant_id"])
        config = booking.get("self_checkin_config") or {}
        if not config and prop:
            prop_sc_config = prop.get("self_checkin_config") or {}
            config = prop_sc_config if isinstance(prop_sc_config, dict) else {}
        steps_completed = booking.get("self_checkin_steps_completed") or {}
        prop_sc_config = (prop or {}).get("self_checkin_config") or {}
        if not isinstance(prop_sc_config, dict):
            prop_sc_config = {}
        arrival_guide = prop_sc_config.get("arrival_guide") or {}

        step_status = _build_step_status(config, steps_completed)

        return JSONResponse(status_code=200, content={
            "status": "already_released",
            "access": {
                "access_code": (prop or {}).get("access_code") or (prop or {}).get("door_code"),
                "door_code": (prop or {}).get("door_code"),
                "wifi_name": (prop or {}).get("wifi_name"),
                "wifi_password": (prop or {}).get("wifi_password"),
            },
            "arrival_guide": arrival_guide,
            "post_entry_steps": step_status["post_entry"],
        })

    booking_id = booking["booking_id"]
    tenant_id = booking["tenant_id"]
    property_id = booking["property_id"]
    config = booking.get("self_checkin_config") or {}
    steps_completed = booking.get("self_checkin_steps_completed") or {}

    from services.self_checkin_service import (
        evaluate_access_release,
        execute_access_release,
        evaluate_and_create_followup,
    )

    result = evaluate_access_release(
        db=db,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        config=config,
        steps_completed=steps_completed,
    )

    if not result.granted:
        reason = result.reason
        reason_code = reason.split(":")[0]
        friendly_messages = {
            "too_early": "It's a little early! Access will open from the official check-in time.",
            "before_checkin_date": "Check-in day isn't here yet. Your access will be ready on the day.",
            "property_not_ready": "Our team is still preparing the property. Please wait a few minutes and try again.",
            "prior_stay_unresolved": "The property is not yet clear. Our team has been notified and will assist you shortly.",
            "pre_access_incomplete": "Please complete all required steps before accessing the property.",
            "approval_revoked": "Self check-in approval has been withdrawn. Please contact the host.",
        }
        friendly = friendly_messages.get(
            reason_code,
            "Access is not available at this time. Please try again or contact your host.",
        )
        return JSONResponse(status_code=200, content={
            "status": "access_denied",
            "reason": reason,
            "friendly_message": friendly,
            "retry_in_seconds": 60,
        })

    # === Gate 1 PASSED — execute access release ===
    release = execute_access_release(
        db=db,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
    )

    # Build post-entry step checklist for the guest's next actions after entry
    from services.self_checkin_service import resolve_post_entry_steps, _STEP_LABELS
    post_entry_required = result.post_entry_steps_required or []
    post_entry_completed = result.post_entry_steps_completed or {}

    post_entry_items = []
    for step_key in post_entry_required:
        post_entry_items.append({
            "key": step_key,
            "label": _STEP_LABELS.get(step_key, step_key),
            "completed": bool(post_entry_completed.get(step_key)),
            "instruction": (config.get("step_instructions") or {}).get(
                step_key, _default_instruction(step_key)
            ),
        })

    # Evaluate follow-up (checks post-entry steps)
    followup = evaluate_and_create_followup(
        db=db,
        tenant_id=tenant_id,
        booking_id=booking_id,
        property_id=property_id,
        config=config,
        steps_completed=steps_completed,
    )

    return JSONResponse(status_code=200, content={
        "status": "access_granted",
        "access": {
            "access_code": result.access_code,
            "door_code": result.door_code,
            "wifi_name": result.wifi_name,
            "wifi_password": result.wifi_password,
        },
        "arrival_guide": result.arrival_guide or {},
        "post_entry_checklist": {
            "items": post_entry_items,
            "all_complete": len(post_entry_items) == 0,
        },
        "checked_in_at": release.get("checked_in_at"),
        "guest_portal_url": release.get("guest_portal_url"),
        "guest_portal_message": (
            "You're checked in! Tap the link above to open your full stay portal "
            "with house info, local tips, and assistance during your stay."
            if release.get("guest_portal_url") else None
        ),
        "followup_status": followup.get("status"),
    })


# ===========================================================================
# POST /self-checkin/{token}/post-entry/{step_key}
# ===========================================================================

@router.post(
    "/self-checkin/{token}/post-entry/{step_key}",
    summary="Submit a post-entry step (Phase 1012)",
    status_code=200,
)
async def submit_post_entry_step(
    token: str,
    step_key: str,
    photo: Optional[UploadFile] = File(None),
    body: dict = {},
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Submit a post-entry step (Gate 2). These steps are completed after the guest
    has entered the property. They are non-blocking — access was already released.

    Access must already be released (sc_status: access_released, completed, followup_required).

    Handles:
    - electricity_meter: text or photo confirmation
    - arrival_photos: property condition baseline photos
    - Custom steps defined in property config

    Photo goes to 'guest-identity/{booking_id}/post-entry/{step_key}.*'
    """
    db = client or _get_db()
    claims, err = _verify_self_checkin_token(token, db=db)
    if err:
        return make_error_response(status_code=401, code="TOKEN_INVALID", extra={"detail": err})

    booking_id = claims.get("entity_id") or claims.get("booking_id")
    if not booking_id:
        return make_error_response(status_code=401, code="TOKEN_INVALID", extra={"detail": "Invalid token"})

    booking = _get_booking_for_portal(db, booking_id)
    if not booking:
        return make_error_response(status_code=404, code=ErrorCode.NOT_FOUND, extra={"detail": "Booking not found"})

    sc_status = booking.get("self_checkin_status") or "none"
    if sc_status not in ("access_released", "completed", "followup_required"):
        return make_error_response(
            status_code=409, code="NOT_YET_ENTERED",
            extra={"detail": "Post-entry steps can only be submitted after access has been released."},
        )

    # Validate step_key against property config
    config = booking.get("self_checkin_config") or {}
    from services.self_checkin_service import resolve_post_entry_steps
    valid_post_entry_steps = resolve_post_entry_steps(config)
    if step_key not in valid_post_entry_steps:
        return make_error_response(
            status_code=400, code="UNKNOWN_STEP",
            extra={
                "detail": f"'{step_key}' is not a configured post-entry step.",
                "valid_steps": valid_post_entry_steps,
            },
        )

    tenant_id = booking["tenant_id"]
    steps = booking.get("self_checkin_steps_completed") or {}
    now = _now_iso()

    step_data: dict = {"completed_at": now}

    # Handle photo upload if provided
    if photo and photo.filename:
        try:
            content = await photo.read()
            ext = photo.filename.rsplit(".", 1)[-1] if "." in photo.filename else "jpg"
            path = f"{booking_id}/post-entry/{step_key}.{ext}"
            db.storage.from_("guest-identity").upload(
                path, content,
                file_options={"content-type": photo.content_type or "image/jpeg"},
            )
            step_data["storage_path"] = path
        except Exception as exc:
            logger.warning("self_checkin: post-entry photo upload failed for %s: %s", step_key, exc)
            step_data["upload_error"] = str(exc)

    # Merge any additional body data (e.g., meter reading text)
    if body.get("value"):
        step_data["value"] = str(body["value"])[:500]
    if body.get("note"):
        step_data["note"] = str(body["note"])[:500]

    steps[step_key] = step_data

    db.table("booking_state").update({
        "self_checkin_steps_completed": steps,
        "updated_at_ms": _now_ms(),
    }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

    # Re-evaluate follow-up: if all post-entry steps are now done, upgrade to completed
    from services.self_checkin_service import check_post_entry_complete

    all_post_done, still_missing = check_post_entry_complete(config, steps)
    if all_post_done and config.get("followup_if_incomplete", True):
        db.table("booking_state").update({
            "self_checkin_status": "completed",
            "self_checkin_completed_at": now,
            "updated_at_ms": _now_ms(),
        }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

    return JSONResponse(status_code=200, content={
        "status": "step_submitted",
        "step_key": step_key,
        "steps_completed": list(steps.keys()),
        "post_entry_remaining": still_missing,
        "all_complete": all_post_done,
    })
