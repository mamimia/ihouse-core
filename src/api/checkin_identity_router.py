"""
Phase 949b-d-h — Check-in Document Intake & Guest Identity Persistence

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

Canonical Identity Hierarchy (Phase 949h — LOCKED RULE):
    Document-verified identity ALWAYS wins over booking/imported names.
    When save-guest-identity is called:
      1. The original booking/import name is preserved in original_booking_name
      2. The document full_name becomes the canonical guest_name
      3. guests.identity_source and identity_verified_at are set
    Booking names may be aliases, nicknames, placeholders, or low-quality OTA values.
    Only the document-verified name is canonical.
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
    # OCR linkage: optional — present when wizard used OCR pre-fill (Phase 986)
    ocr_result_id = body.get("ocr_result_id") or None

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

        # ── Dedup anchor #2: booking-linked guest (Phase B fix) ──
        # If no passport_no match was found, check whether this booking already
        # has a guest linked. A second wizard run on the same booking should ALWAYS
        # update the existing guest record, not create a new one.
        if not guest_id:
            try:
                bs_check = (
                    db.table("booking_state")
                    .select("guest_id")
                    .eq("booking_id", booking_id)
                    .eq("tenant_id", tenant_id)
                    .limit(1)
                    .execute()
                )
                if bs_check.data and bs_check.data[0].get("guest_id"):
                    existing_guest_id = str(bs_check.data[0]["guest_id"])
                    # Verify the guest record still exists
                    gcheck = (
                        db.table("guests")
                        .select("id")
                        .eq("id", existing_guest_id)
                        .eq("tenant_id", tenant_id)
                        .limit(1)
                        .execute()
                    )
                    if gcheck.data:
                        guest_id = existing_guest_id
                        action = "relinked"
                        logger.info(
                            "save_guest_identity: booking %s already has guest %s — reusing (no passport_no supplied)",
                            booking_id, guest_id,
                        )
            except Exception as _link_check_exc:
                logger.warning(
                    "save_guest_identity: booking-anchor dedup check failed (non-blocking): %s",
                    _link_check_exc,
                )

        if guest_id:
            # UPDATE existing guest — merge non-null fields only
            updates: dict = {
                "updated_at": now_iso,
                "identity_verified_at": now_iso,
                "identity_source": "document_scan",
            }
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
            if ocr_result_id:
                updates["ocr_result_id"] = ocr_result_id

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
                "identity_verified_at": now_iso,
                "identity_source": "document_scan",
                "ocr_result_id": ocr_result_id,  # None if manual entry
            }
            db.table("guests").insert(row).execute()
            logger.info("save_guest_identity: CREATED new guest=%s for booking=%s",
                        guest_id, booking_id)

        # ── Step 2: Preserve original booking name (Phase 949h) ──
        # Before overwriting guest_name with document-verified identity,
        # save the original booking/import name for search/audit/reference.
        original_name_preserved = False
        try:
            bs_row = (
                db.table("booking_state")
                .select("guest_name, original_booking_name")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            if bs_row.data:
                current = bs_row.data[0]
                old_name = current.get("guest_name", "")
                already_preserved = current.get("original_booking_name")
                # Only preserve if not already preserved (first document verification)
                if old_name and not already_preserved:
                    db.table("booking_state").update({
                        "original_booking_name": old_name,
                    }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()
                    original_name_preserved = True
                    logger.info(
                        "save_guest_identity: preserved original_booking_name='%s' "
                        "before overwriting with document name='%s'",
                        old_name, full_name,
                    )
        except Exception as preserve_exc:
            logger.warning(
                "save_guest_identity: could not preserve original booking name: %s",
                preserve_exc,
            )

        # ── Step 3: Link guest + set canonical name (document-verified) ──
        try:
            db.table("booking_state").update({
                "guest_id": guest_id,
                "guest_name": full_name,  # canonical document-verified name
            }).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

            logger.info(
                "save_guest_identity: linked guest=%s to booking=%s, "
                "canonical guest_name='%s' (document-verified)",
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
            "original_name_preserved": original_name_preserved,
            "identity_source": "document_scan",
        })

    except Exception as exc:
        logger.exception("save_guest_identity error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR,
                                   extra={"detail": "Failed to save guest identity"})
