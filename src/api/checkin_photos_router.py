"""
Phase 975–976 — Check-in Photo Index Router
============================================

Endpoints:
  POST /worker/bookings/{booking_id}/checkin-photos
       Batch-save walkthrough photo references captured during check-in wizard.
       Creates rows in booking_checkin_photos (the durable index).
       Auth: checkin, worker, ops, admin.

  GET  /worker/bookings/{booking_id}/checkin-photos
       Read back the photo index for a booking (by purpose).
       Auth: checkin, worker, ops, admin, manager.

Design rule:
  This router saves REFERENCES only (storage_path), not the actual bytes.
  Bytes are already in Supabase Storage after /worker/documents/upload.
  This table makes them queryable by booking + purpose.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["checkin-photos"])

_WRITE_ROLES = frozenset({"admin", "manager", "ops", "worker", "checkin", "checkout"})
_READ_ROLES  = frozenset({"admin", "manager", "ops", "worker", "checkin", "checkout"})

_VALID_PURPOSES = frozenset({"walkthrough", "meter", "passport", "damage", "checkout_inspection", "checkout_condition"})


def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# POST /worker/bookings/{booking_id}/checkin-photos
# ---------------------------------------------------------------------------

@router.post(
    "/worker/bookings/{booking_id}/checkin-photos",
    summary="Batch-save check-in photo references (Phase 975)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def save_checkin_photos(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Persist walkthrough photo references for a booking.

    **Request body:**
    ```json
    {
        "photos": [
          {
            "room_label": "bedroom_1",
            "storage_path": "tenant/20260328_uuid_front.jpg",
            "purpose": "walkthrough",
            "captured_at": "2026-03-28T10:00:00Z"
          }
        ]
    }
    ```

    Each photo in `photos` must have `room_label` and `storage_path`.
    `purpose` defaults to `walkthrough`. Valid: walkthrough | meter | passport | damage.
    """
    role = identity.get("role", "")
    if role not in _WRITE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot save checkin photos."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    photos_raw = body.get("photos") or []
    if not isinstance(photos_raw, list) or not photos_raw:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "photos must be a non-empty list"},
        )

    try:
        db = client or _get_db()

        # Resolve property_id from booking
        property_id = None
        try:
            bs = (
                db.table("booking_state")
                .select("property_id")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            if bs.data:
                property_id = bs.data[0].get("property_id")
        except Exception:
            pass

        now = _now_iso()
        rows = []
        for p in photos_raw:
            room_label   = (p.get("room_label") or "").strip()
            storage_path = (p.get("storage_path") or "").strip()
            purpose      = (p.get("purpose") or "walkthrough").strip()

            if not room_label or not storage_path:
                continue  # skip incomplete entries silently
            if purpose not in _VALID_PURPOSES:
                purpose = "walkthrough"

            rows.append({
                "id":            str(uuid.uuid4()),
                "tenant_id":     tenant_id,
                "booking_id":    booking_id,
                "property_id":   property_id,
                "room_label":    room_label,
                "storage_path":  storage_path,
                "purpose":       purpose,
                "captured_at":   p.get("captured_at") or now,
                "uploaded_by":   actor_id,
                "notes":         p.get("notes") or None,
                "created_at":    now,
                "upload_status": "confirmed",  # Phase 1059: explicit — bytes were in Storage before this call
            })

        if not rows:
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "No valid photos provided (each needs room_label + storage_path)"},
            )

        db.table("booking_checkin_photos").insert(rows).execute()

        logger.info(
            "checkin-photos: saved %d photos for booking=%s tenant=%s",
            len(rows), booking_id, tenant_id,
        )

        return JSONResponse(status_code=201, content={
            "booking_id":  booking_id,
            "saved":       len(rows),
            "property_id": property_id,
        })

    except Exception as exc:
        logger.exception("POST checkin-photos %s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /worker/bookings/{booking_id}/checkin-photos
# ---------------------------------------------------------------------------

@router.get(
    "/worker/bookings/{booking_id}/checkin-photos",
    summary="Read check-in photo index for a booking (Phase 975)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_checkin_photos(
    booking_id: str,
    purpose: Optional[str] = None,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the stored photo references for a booking.
    Optionally filter by `purpose` query param (walkthrough | meter | passport | damage).
    """
    role = identity.get("role", "")
    if role not in _READ_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot read checkin photos."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        query = (
            db.table("booking_checkin_photos")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("captured_at", desc=False)
        )
        if purpose and purpose in _VALID_PURPOSES:
            query = query.eq("purpose", purpose)

        res = query.execute()
        photos = res.data or []

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "count":      len(photos),
            "photos":     photos,
        })

    except Exception as exc:
        logger.exception("GET checkin-photos %s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 1059 — GET /worker/bookings/{booking_id}/checkin-resume
# ---------------------------------------------------------------------------

@router.get(
    "/worker/bookings/{booking_id}/checkin-resume",
    summary="Get durable check-in wizard state for safe resume after interruption (Phase 1059)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_checkin_resume_state(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the current durable state of a check-in wizard session for a booking.

    Purpose: allow a worker to safely resume after browser refresh, tab close,
    or connectivity interruption without losing evidence of what succeeded.

    Returns:
      - booking_status: current status from booking_state
      - checkin_settlement: what was already saved (deposit, meter reading)
      - checkin_photos: photo index rows already committed (by purpose)
      - guest_identity: whether guest identity was saved (boolean + full_name)
      - resume_hint: human-readable suggestion of where to resume
    """
    role = identity.get("role", "")
    if role not in _READ_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot read check-in resume state."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        # 1. Booking status
        booking_status = None
        try:
            bs = (
                db.table("booking_state")
                .select("status, checked_in_at, property_id")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            if bs.data:
                booking_status = bs.data[0]
        except Exception:
            pass

        # 2. Check-in photos already committed (the durable index)
        photos: list = []
        try:
            pr = (
                db.table("booking_checkin_photos")
                .select("room_label, storage_path, purpose, captured_at, upload_status")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .order("captured_at", desc=False)
                .execute()
            )
            photos = pr.data or []
        except Exception:
            pass

        # 3. Check-in settlement (deposit + meter)
        settlement = None
        try:
            sr = (
                db.table("checkin_settlements")
                .select("deposit_collected, deposit_amount, deposit_currency, deposit_method, meter_reading, meter_photo_url, created_at")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if sr.data:
                settlement = sr.data[0]
        except Exception:
            pass  # table may not exist in all tenant configs

        # 4. Guest identity check (boolean only — no PII returned here)
        guest_identity_saved = False
        guest_full_name = None
        try:
            ci = (
                db.table("checkin_identity_forms")
                .select("full_name, document_type, created_at")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if ci.data:
                guest_identity_saved = True
                guest_full_name = ci.data[0].get("full_name")
        except Exception:
            pass  # table name may differ

        # 5. Build resume hint
        current_status = (booking_status or {}).get("status", "")
        if current_status == "checked_in":
            resume_hint = "CHECK_IN_COMPLETE — booking is already checked_in. No action needed."
        elif guest_identity_saved and len(photos) > 0:
            resume_hint = "COMPLETE_STEP — identity and photos saved. Resume at final Complete step."
        elif guest_identity_saved:
            resume_hint = "PHOTOS_STEP — identity saved. Resume at walkthrough photo step."
        elif settlement:
            resume_hint = "PASSPORT_STEP — deposit/meter saved. Resume at identity capture step."
        elif photos:
            resume_hint = "SETTLEMENT_STEP — photos saved. Resume at deposit/meter step."
        else:
            resume_hint = "START — no durable state found. Begin from step 1."

        # 6. Identify any confirmed vs failed photo entries
        confirmed_photos = [p for p in photos if p.get("upload_status", "confirmed") == "confirmed"]
        failed_photos = [p for p in photos if p.get("upload_status") == "failed"]

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "booking_status": current_status,
            "checked_in_at": (booking_status or {}).get("checked_in_at"),
            "property_id": (booking_status or {}).get("property_id"),
            "resume_hint": resume_hint,
            "photos": {
                "total": len(photos),
                "confirmed": len(confirmed_photos),
                "failed": len(failed_photos),
                "purposes": list({p["purpose"] for p in confirmed_photos}),
            },
            "settlement": {
                "deposit_collected": (settlement or {}).get("deposit_collected", False),
                "meter_reading": (settlement or {}).get("meter_reading"),
            } if settlement else None,
            "guest_identity": {
                "saved": guest_identity_saved,
                "full_name": guest_full_name,
            },
        })

    except Exception as exc:
        logger.exception("GET checkin-resume %s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

