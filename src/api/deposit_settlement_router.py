"""
Phases 687–690 — Deposit Settlement & Checkout Completion
==========================================================

687: POST /deposits — collect deposit
     POST /deposits/{deposit_id}/return — full return
     GET  /deposits?booking_id= — lookup

688: POST /deposits/{deposit_id}/deductions — add deduction
     DELETE /deposits/{deposit_id}/deductions/{deduction_id}
     GET  /deposits/{deposit_id}/settlement — breakdown

689: GET /bookings/{booking_id}/photo-comparison — side-by-side photos

690: POST /bookings/{booking_id}/checkout — enhanced with settlement pre-check

Invariant:
    This router NEVER writes to event_log or booking_financial_facts.
    Deposit records are independent — financial integration is deferred.
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
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
        if deposit["status"] == "returned":
            return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "Deposit already returned."})

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
        if dep_rows[0]["status"] == "returned":
            return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "Cannot deduct from returned deposit."})

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
        cleaning = (
            db.table("cleaning_task_photos").select("photo_url, room_label, created_at")
            .eq("booking_id", booking_id)
            .order("created_at")
            .execute()
        )
        cleaning_photos = cleaning.data or []

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
# Phase 690 — Checkout Completion with Settlement Pre-Check
# ===========================================================================

@router.post("/bookings/{booking_id}/checkout", summary="Complete checkout (Phase 690)")
async def complete_checkout(
    booking_id: str, body: Optional[Dict[str, Any]] = None,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    body = body or {}
    worker_id = str(body.get("worker_id") or tenant_id).strip()
    force = body.get("force", False)

    try:
        db = client if client is not None else _get_db()

        # Check booking exists
        booking_res = db.table("bookings").select("booking_id, status, property_id").eq("booking_id", booking_id).limit(1).execute()
        booking_rows = booking_res.data or []
        if not booking_rows:
            return make_error_response(404, "NOT_FOUND", extra={"detail": f"Booking '{booking_id}' not found."})

        booking = booking_rows[0]
        if booking.get("status") == "checked_out" and not force:
            return make_error_response(400, ErrorCode.VALIDATION_ERROR, extra={"detail": "Already checked out."})

        # Pre-check: deposit settlement
        deposit_warning = None
        dep_res = db.table("cash_deposits").select("id, status, refund_amount").eq("booking_id", booking_id).execute()
        deposits = dep_res.data or []
        unsettled = [d for d in deposits if d["status"] == "collected"]
        if unsettled and not force:
            deposit_warning = f"{len(unsettled)} unsettled deposit(s). Return or settle before checkout, or use force=true."
            return make_error_response(400, ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": deposit_warning, "unsettled_deposits": unsettled})

        now = _now_iso()
        # Update booking status
        db.table("bookings").update({
            "status": "checked_out",
            "checked_out_by": worker_id,
            "checked_out_at": now,
        }).eq("booking_id", booking_id).execute()

        # Auto-create CLEANING task (best-effort)
        try:
            from tasks.task_model import Task
            from tasks.task_automator import create_task_if_needed
            cleaning_task = Task.build(
                task_kind="CLEANING",
                booking_id=booking_id,
                property_id=booking.get("property_id", ""),
                priority="MEDIUM",
                ack_sla_minutes=60,
            )
            create_task_if_needed(db, cleaning_task, tenant_id=tenant_id)
        except Exception:
            logger.warning("Failed to auto-create cleaning task for %s", booking_id)

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="booking",
                              entity_id=booking_id, action="checked_out",
                              details={"worker_id": worker_id, "deposits_count": len(deposits),
                                       "unsettled": len(unsettled), "force": force})
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "booking_id": booking_id,
            "status": "checked_out",
            "checked_out_by": worker_id,
            "checked_out_at": now,
            "deposit_warning": deposit_warning,
        })
    except Exception as exc:
        logger.exception("complete_checkout error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR)
