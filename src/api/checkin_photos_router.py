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
                "id":           str(uuid.uuid4()),
                "tenant_id":    tenant_id,
                "booking_id":   booking_id,
                "property_id":  property_id,
                "room_label":   room_label,
                "storage_path": storage_path,
                "purpose":      purpose,
                "captured_at":  p.get("captured_at") or now,
                "uploaded_by":  actor_id,
                "notes":        p.get("notes") or None,
                "created_at":   now,
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
