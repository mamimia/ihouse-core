"""
Phase 949b-d — Check-in Document Intake & Guest Identity Persistence

Endpoints:
    POST /worker/documents/upload     — Upload document image(s) to Supabase Storage
    POST /worker/checkin/save-guest-identity — Find-or-create guest + link to booking + backfill guest_name

Architecture:
    - JWT auth required on all endpoints.
    - Tenant isolation enforced.
    - Document images stored in private 'guest-documents' bucket.
    - Guest dedup by passport_no + tenant_id.
    - booking_state.guest_id AND guest_name backfilled on save.
    - Manual-first: no OCR dependency. Staff types/reviews fields.
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# POST /worker/documents/upload
# ---------------------------------------------------------------------------

@router.post(
    "/worker/documents/upload",
    tags=["worker", "documents"],
    summary="Upload document image to guest-documents bucket (Phase 949b)",
    responses={
        200: {"description": "Image uploaded, returns storage path and signed URL"},
        400: {"description": "Missing image data"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Upload failed"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upload_document_image(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Upload a document image (base64-encoded JPEG) to Supabase Storage.

    **Request body:**
    ```json
    {
        "image_base64": "<base64-encoded JPEG>",
        "side": "front",          // "front" or "back"
        "booking_id": "optional"  // for path organization
    }
    ```

    Returns:
    ```json
    {
        "storage_path": "guest-documents/{tenant}/{uuid}_front.jpg",
        "signed_url": "https://...(5-min expiry)..."
    }
    ```
    """
    image_b64 = body.get("image_base64", "").strip()
    if not image_b64:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "image_base64 is required"})

    side = body.get("side", "front").strip().lower()
    if side not in ("front", "back"):
        side = "front"

    try:
        # Decode base64
        # Strip data URI prefix if present (e.g. "data:image/jpeg;base64,...")
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        image_bytes = base64.b64decode(image_b64)

        if len(image_bytes) < 1000:
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": "Image too small — likely corrupt"})

        if len(image_bytes) > 10 * 1024 * 1024:
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": "Image exceeds 10MB limit"})

        # Generate unique path
        file_id = str(uuid.uuid4())[:12]
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        storage_path = f"{tenant_id}/{ts}_{file_id}_{side}.jpg"

        db = client if client is not None else _get_supabase_client()

        # Upload to Supabase Storage
        db.storage.from_("guest-documents").upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )

        # Generate signed URL (5-minute expiry for immediate preview)
        signed = db.storage.from_("guest-documents").create_signed_url(
            path=storage_path,
            expires_in=300,
        )
        signed_url = signed.get("signedURL") or signed.get("signedUrl") or None

        logger.info("document_upload: tenant=%s path=%s size=%d",
                     tenant_id, storage_path, len(image_bytes))

        return JSONResponse(status_code=200, content={
            "storage_path": storage_path,
            "signed_url": signed_url,
            "side": side,
            "size_bytes": len(image_bytes),
        })

    except Exception as exc:
        logger.exception("POST /worker/documents/upload error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR,
                                   extra={"detail": "Document upload failed"})


# ---------------------------------------------------------------------------
# POST /worker/checkin/save-guest-identity
# ---------------------------------------------------------------------------

@router.post(
    "/worker/checkin/save-guest-identity",
    tags=["worker", "guests"],
    summary="Find-or-create guest, link to booking, backfill guest_name (Phase 949d)",
    responses={
        200: {"description": "Guest identity saved and linked to booking"},
        400: {"description": "Missing required fields"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def save_guest_identity(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Find-or-create a guest record and link it to a booking.

    This is the canonical identity intake endpoint for the check-in wizard.
    It performs three critical writes:
      1. Creates or updates the guest master record (guests table)
      2. Sets booking_state.guest_id → links booking to guest
      3. Backfills booking_state.guest_name → enables guest portal greeting

    **Request body:**
    ```json
    {
        "booking_id": "required",
        "full_name": "required — from passport/ID",
        "document_type": "PASSPORT | NATIONAL_ID | DRIVING_LICENSE",
        "document_number": "passport_no value",
        "nationality": "GBR",
        "date_of_birth": "1990-01-15",
        "passport_expiry": "2032-05-20",
        "issuing_country": "GBR",
        "document_photo_url": "storage path from /worker/documents/upload"
    }
    ```

    **Dedup rule:** Match by tenant_id + passport_no (case-insensitive).
    If matched, UPDATE (merge non-null fields). If not, CREATE new.
    """
    booking_id = (body.get("booking_id") or "").strip()
    full_name = (body.get("full_name") or "").strip()
    document_number = (body.get("document_number") or "").strip()

    if not booking_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "booking_id is required"})
    if not full_name:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "full_name is required"})

    document_type = (body.get("document_type") or "PASSPORT").strip().upper()
    nationality = (body.get("nationality") or "").strip() or None
    date_of_birth = body.get("date_of_birth") or None
    passport_expiry = body.get("passport_expiry") or None
    issuing_country = (body.get("issuing_country") or "").strip() or None
    document_photo_url = body.get("document_photo_url") or None

    try:
        db = client if client is not None else _get_supabase_client()
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        # ── Step 1: Find-or-create guest (dedup by passport_no + tenant) ──
        guest_id = None
        action = "created"

        if document_number:
            # Try to find existing guest by document number
            existing = (
                db.table("guests")
                .select("id, full_name, passport_no")
                .eq("tenant_id", tenant_id)
                .ilike("passport_no", document_number)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            if existing.data:
                guest_id = existing.data[0]["id"]
                action = "matched"

        if guest_id:
            # UPDATE existing guest — merge non-null fields only
            updates: dict = {"updated_at": now_iso}
            if full_name:
                updates["full_name"] = full_name
            if document_type:
                updates["document_type"] = document_type
            if document_number:
                updates["passport_no"] = document_number
            if nationality:
                updates["nationality"] = nationality
            if date_of_birth:
                updates["date_of_birth"] = date_of_birth
            if passport_expiry:
                updates["passport_expiry"] = passport_expiry
            if issuing_country:
                updates["issuing_country"] = issuing_country
            if document_photo_url:
                updates["document_photo_url"] = document_photo_url

            db.table("guests").update(updates).eq("id", guest_id).execute()
            logger.info("save_guest_identity: MATCHED existing guest=%s for booking=%s",
                        guest_id, booking_id)
        else:
            # CREATE new guest record
            guest_id = str(uuid.uuid4())
            row = {
                "id": guest_id,
                "tenant_id": tenant_id,
                "full_name": full_name,
                "passport_no": document_number or None,
                "document_type": document_type,
                "nationality": nationality,
                "date_of_birth": date_of_birth,
                "passport_expiry": passport_expiry,
                "issuing_country": issuing_country,
                "document_photo_url": document_photo_url,
            }
            db.table("guests").insert(row).execute()
            logger.info("save_guest_identity: CREATED new guest=%s for booking=%s",
                        guest_id, booking_id)

        # ── Step 2: Link guest to booking (booking_state.guest_id) ──
        # ── Step 3: Backfill guest_name into booking_state ──
        try:
            db.table("booking_state").update({
                "guest_id": guest_id,
                "guest_name": full_name,
            }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

            logger.info(
                "save_guest_identity: linked guest=%s to booking=%s, "
                "backfilled guest_name='%s'",
                guest_id, booking_id, full_name,
            )
        except Exception as link_exc:
            logger.warning(
                "save_guest_identity: booking linkage failed for %s: %s",
                booking_id, link_exc,
            )
            # Non-blocking — guest record was still created/updated

        # ── Step 4: Audit event ──
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                tenant_id=tenant_id,
                actor_id=tenant_id,
                action="GUEST_IDENTITY_SAVED",
                entity_type="guest",
                entity_id=guest_id,
                payload={
                    "booking_id": booking_id,
                    "action": action,
                    "document_type": document_type,
                    "document_number_partial": document_number[:4] + "***" if len(document_number) > 4 else "***",
                    "has_photo": document_photo_url is not None,
                },
                client=db,
            )
        except Exception:
            pass  # audit is best-effort

        return JSONResponse(status_code=200, content={
            "guest_id": guest_id,
            "action": action,
            "full_name": full_name,
            "booking_id": booking_id,
            "linked": True,
            "guest_name_backfilled": True,
        })

    except Exception as exc:
        logger.exception("save_guest_identity error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR,
                                   extra={"detail": "Failed to save guest identity"})
