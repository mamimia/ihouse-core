"""
Phases 687–689 — Deposit Settlement & Photo Comparison
=======================================================

687: POST /deposits                           — collect deposit
     POST /deposits/{deposit_id}/return      — return deposit (full or post-deductions)
     POST /deposits/{deposit_id}/forfeit     — forfeit deposit (property keeps it)
     GET  /deposits?booking_id=              — lookup

688: POST /deposits/{deposit_id}/deductions   — add deduction
     DELETE /deposits/{deposit_id}/deductions/{deduction_id}
     GET  /deposits/{deposit_id}/settlement  — breakdown

689: GET /bookings/{booking_id}/photo-comparison — side-by-side photos
692: POST /bookings/{booking_id}/checkout-photos/upload — write checkout condition photos

NOTE — Phase 690 checkout endpoint REMOVED:
    POST /bookings/{booking_id}/checkout was previously defined here (Phase 690)
    and is now REMOVED. The canonical implementation lives in:
        src/api/booking_checkin_router.py (Phase 398)
    That implementation:
      - Writes to booking_state (not bookings directly)
      - Emits BOOKING_CHECKED_OUT to event_log (best-effort)
      - Enforces checkout role guard (_assert_checkout_role)
      - Creates CLEANING task via task_writer
    The Phase 690 shadow route was incorrect: it wrote to the wrong table,
    bypassed event_log, and lacked a role guard. It was masked by FastAPI's
    first-registration-wins behavior (booking_checkin_router registered first),
    but its existence was fragile and misleading.

    If deposit settlement pre-check before checkout is needed (the original
    Phase 690 intent), that logic should be integrated into
    booking_checkin_router.checkout_booking() as a pre-flight query.

Deposit lifecycle statuses:
    collected  → initial state after collection
    returned   → deposit returned to guest (full or partial after deductions)
    forfeited  → property deliberately retains the deposit (damage / breach)

Terminal states: returned, forfeited — no further writes allowed.

Invariant:
    This router NEVER writes to event_log, booking_financial_facts, or booking_state.
    Deposit records are independent — financial integration is deferred.
    Booking status transitions are owned exclusively by booking_checkin_router.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["checkout"])


def _get_db() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ===========================================================================
# Phase 687 — Deposit Collection & Return
# ===========================================================================

@router.post("/deposits", summary="Collect cash deposit (Phase 687)")
async def collect_deposit(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    booking_id = str(body.get("booking_id") or "").strip()
    amount = body.get("amount")
    currency = str(body.get("currency") or "THB").upper()
    collected_by = str(body.get("collected_by") or tenant_id).strip()
    notes = str(body.get("notes") or "").strip() or None

    if not booking_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "booking_id required"})
    if not isinstance(amount, (int, float)) or amount <= 0:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "amount must be positive number"})

    now = _now_iso()
    deposit_id = hashlib.sha256(f"DEP:{booking_id}:{now}".encode()).hexdigest()[:16]
    row = {
        "id": deposit_id,
        "booking_id": booking_id,
        "tenant_id": tenant_id,
        "amount": float(amount),
        "currency": currency,
        "status": "collected",
        "collected_by": collected_by,
        "collected_at": now,
        "notes": notes,
        "refund_amount": float(amount),  # Initially full refund
        "created_at": now,
    }

    try:
        db = client if client is not None else _get_db()
        result = db.table("cash_deposits").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(500, ErrorCode.INTERNAL_ERROR)

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="deposit",
                              entity_id=deposit_id, action="collected",
                              details={"booking_id": booking_id, "amount": amount, "currency": currency})
        except Exception:
            pass

        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("collect_deposit error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.post("/deposits/{deposit_id}/return", summary="Full deposit return (Phase 687)")
async def return_deposit(
    deposit_id: str, body: Optional[Dict[str, Any]] = None,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    body = body or {}
    returned_by = str(body.get("returned_by") or tenant_id).strip()

    try:
        db = client if client is not None else _get_db()

        cur = db.table("cash_deposits").select("status, amount, refund_amount").eq("id", deposit_id).limit(1).execute()
        cur_rows = cur.data or []
        if not cur_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Deposit '{deposit_id}' not found."})

        deposit = cur_rows[0]
        if deposit["status"] in ("returned", "forfeited"):
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Deposit already in terminal state: {deposit['status']}."},
            )

        now = _now_iso()
        update = {"status": "returned", "returned_by": returned_by, "returned_at": now}
        result = db.table("cash_deposits").update(update).eq("id", deposit_id).execute()
        rows = result.data or []

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="deposit",
                              entity_id=deposit_id, action="returned",
                              details={"refund_amount": deposit.get("refund_amount", deposit["amount"])})
        except Exception:
            pass

        return JSONResponse(status_code=200, content=rows[0] if rows else {"id": deposit_id, "status": "returned"})
    except Exception as exc:
        logger.exception("return_deposit error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.post("/deposits/{deposit_id}/forfeit", summary="Forfeit deposit — property retains it (Phase 691)")
async def forfeit_deposit(
    deposit_id: str, body: Optional[Dict[str, Any]] = None,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Mark a deposit as forfeited — the property retains the full (or remaining)
    deposit amount due to guest damage, breach of contract, or other cause.

    This closes the deposit lifecycle without returning funds to the guest.
    Terminal state: no further writes (return, deductions) are allowed after forfeiture.

    **Request body (all optional):**
    ```json
    { "forfeited_by": "worker_id", "reason": "Property damage — broken TV" }
    ```
    """
    body = body or {}
    forfeited_by = str(body.get("forfeited_by") or tenant_id).strip()
    reason = str(body.get("reason") or "").strip() or None

    try:
        db = client if client is not None else _get_db()

        cur = db.table("cash_deposits").select("status, amount, refund_amount").eq("id", deposit_id).limit(1).execute()
        cur_rows = cur.data or []
        if not cur_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Deposit '{deposit_id}' not found."})

        deposit = cur_rows[0]
        if deposit["status"] in ("returned", "forfeited"):
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Deposit already in terminal state: {deposit['status']}."},
            )

        now = _now_iso()
        # Forfeited amount = whatever was remaining (original minus any deductions already recorded)
        forfeited_amount = deposit.get("refund_amount", deposit["amount"])
        update = {
            "status": "forfeited",
            "forfeited_by": forfeited_by,
            "forfeited_at": now,
            "forfeited_amount": float(forfeited_amount),
            "forfeiture_reason": reason,
        }
        result = db.table("cash_deposits").update(update).eq("id", deposit_id).execute()
        rows = result.data or []

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="deposit",
                              entity_id=deposit_id, action="forfeited",
                              details={
                                  "forfeited_by": forfeited_by,
                                  "forfeited_amount": forfeited_amount,
                                  "reason": reason,
                              })
        except Exception:
            pass

        return JSONResponse(
            status_code=200,
            content=rows[0] if rows else {
                "id": deposit_id,
                "status": "forfeited",
                "forfeited_amount": float(forfeited_amount),
            },
        )
    except Exception as exc:
        logger.exception("forfeit_deposit error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.get("/deposits", summary="Lookup deposits by booking (Phase 687)")
async def list_deposits(
    booking_id: str = Query(...),
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        result = (
            db.table("cash_deposits").select("*")
            .eq("booking_id", booking_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={"count": len(rows), "deposits": rows})
    except Exception as exc:
        logger.exception("list_deposits error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 688 — Deposit Deductions CRUD
# ===========================================================================

@router.post("/deposits/{deposit_id}/deductions", summary="Add deduction (Phase 688)")
async def add_deduction(
    deposit_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    description = str(body.get("description") or "").strip()
    amount = body.get("amount")
    category = str(body.get("category") or "damage").strip()
    photo_url = body.get("photo_url")

    if not description:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "description required"})
    if not isinstance(amount, (int, float)) or amount <= 0:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "amount must be positive"})

    try:
        db = client if client is not None else _get_db()

        # Check deposit exists and is collected
        dep = db.table("cash_deposits").select("id, amount, status").eq("id", deposit_id).limit(1).execute()
        dep_rows = dep.data or []
        if not dep_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Deposit '{deposit_id}' not found."})
        dep_status = dep_rows[0]["status"]
        if dep_status in ("returned", "forfeited"):
            return make_error_response(
                400, ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Cannot add deduction to a deposit in terminal state: {dep_status}."},
            )

        now = _now_iso()
        ded_id = hashlib.sha256(f"DED:{deposit_id}:{description}:{now}".encode()).hexdigest()[:16]
        ded_row = {
            "id": ded_id,
            "deposit_id": deposit_id,
            "description": description,
            "amount": float(amount),
            "category": category,
            "photo_url": photo_url,
            "created_at": now,
        }
        db.table("deposit_deductions").insert(ded_row).execute()

        # Recalculate refund
        all_deds = db.table("deposit_deductions").select("amount").eq("deposit_id", deposit_id).execute()
        total_deducted = sum(d["amount"] for d in (all_deds.data or []))
        original = dep_rows[0]["amount"]
        refund = max(0.0, original - total_deducted)
        db.table("cash_deposits").update({"refund_amount": refund}).eq("id", deposit_id).execute()

        return JSONResponse(status_code=201, content={
            "deduction": ded_row,
            "total_deductions": total_deducted,
            "refund_amount": refund,
        })
    except Exception as exc:
        logger.exception("add_deduction error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.delete("/deposits/{deposit_id}/deductions/{deduction_id}", summary="Remove deduction (Phase 688)")
async def remove_deduction(
    deposit_id: str, deduction_id: str,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()

        # Delete deduction
        db.table("deposit_deductions").delete().eq("id", deduction_id).eq("deposit_id", deposit_id).execute()

        # Recalculate
        dep = db.table("cash_deposits").select("amount").eq("id", deposit_id).limit(1).execute()
        dep_rows = dep.data or []
        if not dep_rows:
            return make_error_response(404, "NOT_FOUND")

        all_deds = db.table("deposit_deductions").select("amount").eq("deposit_id", deposit_id).execute()
        total_deducted = sum(d["amount"] for d in (all_deds.data or []))
        refund = max(0.0, dep_rows[0]["amount"] - total_deducted)
        db.table("cash_deposits").update({"refund_amount": refund}).eq("id", deposit_id).execute()

        return JSONResponse(status_code=200, content={
            "total_deductions": total_deducted,
            "refund_amount": refund,
        })
    except Exception as exc:
        logger.exception("remove_deduction error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


@router.get("/deposits/{deposit_id}/settlement", summary="Deposit settlement breakdown (Phase 688)")
async def get_settlement(
    deposit_id: str,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
        dep = db.table("cash_deposits").select("*").eq("id", deposit_id).limit(1).execute()
        dep_rows = dep.data or []
        if not dep_rows:
            return make_error_response(404, "NOT_FOUND")

        deds = db.table("deposit_deductions").select("*").eq("deposit_id", deposit_id).order("created_at").execute()
        deductions = deds.data or []
        total_deducted = sum(d["amount"] for d in deductions)

        deposit = dep_rows[0]
        return JSONResponse(status_code=200, content={
            "deposit_id": deposit_id,
            "original_amount": deposit["amount"],
            "currency": deposit.get("currency", "THB"),
            "deductions": deductions,
            "total_deductions": total_deducted,
            "refund_amount": deposit.get("refund_amount", deposit["amount"] - total_deducted),
            "status": deposit["status"],
            # Forfeiture fields — populated only when status == "forfeited"
            "forfeited_amount": deposit.get("forfeited_amount"),
            "forfeited_by": deposit.get("forfeited_by"),
            "forfeited_at": deposit.get("forfeited_at"),
            "forfeiture_reason": deposit.get("forfeiture_reason"),
        })
    except Exception as exc:
        logger.exception("get_settlement error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 689 — Photo Comparison
# ===========================================================================

@router.get("/bookings/{booking_id}/photo-comparison", summary="Photo comparison (Phase 689)")
async def photo_comparison(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()

        # Get booking → property_id
        booking = db.table("bookings").select("property_id").eq("booking_id", booking_id).limit(1).execute()
        booking_rows = booking.data or []
        if not booking_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Booking '{booking_id}' not found."})
        property_id = booking_rows[0]["property_id"]

        # Reference photos (property baseline)
        ref = db.table("property_reference_photos").select("photo_url, room_label, caption").eq("property_id", property_id).execute()
        ref_photos = ref.data or []

        # Pre-checkin cleaning photos
        # NOTE: cleaning_task_router.py writes to 'cleaning_photos' (keyed by progress_id),
        # not 'cleaning_task_photos'. We resolve by joining through cleaning_task_progress.
        cleaning_photos: List[Dict[str, Any]] = []
        try:
            progress_res = (
                db.table("cleaning_task_progress")
                .select("id")
                .eq("booking_id", booking_id)
                .limit(1)
                .execute()
            )
            if progress_res.data:
                progress_id = progress_res.data[0]["id"]
                cp_res = (
                    db.table("cleaning_photos")
                    .select("photo_url, room_label, created_at")
                    .eq("progress_id", progress_id)
                    .order("created_at")
                    .execute()
                )
                cleaning_photos = cp_res.data or []
        except Exception:
            cleaning_photos = []

        # Current checkout photos (worker takes during checkout)
        checkout = (
            db.table("checkout_photos").select("photo_url, room_label, created_at, notes")
            .eq("booking_id", booking_id)
            .order("created_at")
            .execute()
        )
        checkout_photos = checkout.data or []

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "property_id": property_id,
            "reference_photos": ref_photos,
            "cleaning_photos": cleaning_photos,
            "checkout_photos": checkout_photos,
        })
    except Exception as exc:
        logger.exception("photo_comparison error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 692 — Checkout Photo Upload
# ===========================================================================

_ALLOWED_CHECKOUT_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
_MAX_CHECKOUT_PHOTO_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/bookings/{booking_id}/checkout-photos/upload",
             summary="Upload checkout condition photo (Phase 692)")
async def upload_checkout_photo(
    booking_id: str,
    file: UploadFile = File(...),
    room_label: str = Form(...),
    notes: str = Form(""),
    taken_by: str = Form(""),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Upload a checkout condition photo for a specific room via FormData.

    This is the write path that populates the `checkout_photos` table,
    enabling the GET /bookings/{id}/photo-comparison endpoint to return
    real post-stay condition photos alongside reference and cleaning photos.

    **Form fields:**
    - `file`: image file (JPEG, PNG, WebP, HEIC — max 10 MB)
    - `room_label`: room identifier, e.g. 'bedroom_1', 'bathroom', 'living_room'
    - `notes`: optional worker annotation for this specific photo
    - `taken_by`: worker ID (optional)
    """
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_CHECKOUT_PHOTO_TYPES:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Invalid file type '{content_type}'. Allowed: JPEG, PNG, WebP, HEIC."},
        )

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_CHECKOUT_PHOTO_SIZE:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"File too large ({len(file_bytes):,} bytes). Max: 10 MB."},
        )

    if not room_label.strip():
        return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "room_label is required."})

    try:
        db = client if client is not None else _get_db()

        # Verify booking exists and belongs to this tenant
        bk = db.table("bookings").select("booking_id").eq("booking_id", booking_id).limit(1).execute()
        if not (bk.data or []):
            return make_error_response(404, "NOT_FOUND",
                                       extra={"detail": f"Booking '{booking_id}' not found."})

        # Upload to Supabase Storage — bucket: checkout-photos
        ext = content_type.split("/")[-1].replace("jpeg", "jpg")
        file_name = f"{tenant_id}/{booking_id}/{room_label.strip()}_{uuid.uuid4().hex[:8]}.{ext}"

        try:
            db.storage.from_("checkout-photos").upload(
                file_name,
                file_bytes,
                {"content-type": content_type},
            )
            supabase_url = os.environ.get("SUPABASE_URL", "")
            photo_url = f"{supabase_url}/storage/v1/object/public/checkout-photos/{file_name}"
        except Exception as storage_exc:
            logger.warning("checkout photo storage upload failed: %s", storage_exc)
            photo_url = f"storage-failed://{booking_id}/{room_label}/{uuid.uuid4().hex[:8]}"

        # Persist record  
        photo_row = {
            "booking_id": booking_id,
            "tenant_id": tenant_id,
            "room_label": room_label.strip(),
            "photo_url": photo_url,
            "notes": notes.strip() or None,
            "taken_by": taken_by.strip() or None,
        }
        result = db.table("checkout_photos").insert(photo_row).execute()
        saved = (result.data or [{}])[0]

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="checkout_photo",
                              entity_id=booking_id, action="uploaded",
                              details={"room_label": room_label.strip(), "taken_by": taken_by.strip() or None})
        except Exception:
            pass

        return JSONResponse(status_code=201, content={
            "uploaded": True,
            "id": saved.get("id"),
            "booking_id": booking_id,
            "room_label": room_label.strip(),
            "photo_url": photo_url,
        })
    except Exception as exc:
        logger.exception("upload_checkout_photo error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 690 — Checkout Completion
# REMOVED: This endpoint has been removed from this router.
#
# The canonical checkout implementation is in booking_checkin_router.py
# (Phase 398) at POST /bookings/{booking_id}/checkout.
#
# That implementation correctly:
#   - Reads from and writes to booking_state (not bookings table directly)
#   - Emits BOOKING_CHECKED_OUT to event_log (best-effort)
#   - Enforces checkout role guard
#   - Creates CLEANING task via task_writer
#
# If deposit pre-check (unsettled deposit warning) before checkout is required,
# add a pre-flight query to booking_checkin_router.checkout_booking().
# ===========================================================================
