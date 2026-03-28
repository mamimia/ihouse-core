"""
Phases 957–958, corrected by 963–964 — Check-in Settlement Capture & Admin Review
===================================================================================

Phase 957 — Worker endpoints for check-in capture.
Phase 958 — Admin review endpoints.
Phase 963 — Hard wizard enforcement: required steps are REJECTED (400) if missing.
Phase 964 — Direct cash_deposits write: deposit goes to the real settlement table
            at check-in time, not a soft operational note.

Worker endpoints:
    POST /worker/bookings/{booking_id}/checkin-settlement
         Hard-enforced capture: deposit + opening meter reading.
         REJECTS (400) if property requires deposit/electricity and worker omits them.
         Writes to:
           - cash_deposits (the REAL deposit, Phase 964)
           - checkin_deposit_records (secondary audit trail)
           - electricity_meter_readings (opening reading)
         Admin override: force_override=true + override_reason bypasses required steps.
         Auth: checkin, ops, worker, admin.

    GET  /worker/bookings/{booking_id}/checkin-settlement
         Read current check-in settlement state (deposit + meter reading).
         Auth: checkin, ops, worker, admin, manager.

    POST /worker/bookings/{booking_id}/meter-reading/correction
         Append-only correction of the opening meter reading.
         Auth: checkin, ops, admin.

Admin endpoints (Phase 958):
    GET  /admin/bookings/{booking_id}/settlement-capture
         Full operational view: charge rule + deposit + meter readings.
         Auth: admin, manager.

Invariants (corrected by Phase 963-964):
    - If property has deposit_enabled=true → deposit_collected MUST be true unless
      force_override=true + override_reason is provided.
    - If property has electricity_enabled=true → meter_reading MUST be provided
      unless force_override=true + override_reason is provided.
    - Deposit is written to cash_deposits (Phase 964): the REAL financial record,
      not a soft operational note. checkin_deposit_records is a secondary trail.
    - electricity_meter_readings is append-only. No UPDATE ever executes on it.
    - All actor IDs are real user_ids from JWT.
    - All mutations write to admin_audit_log.
"""
from __future__ import annotations

import hashlib
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
router = APIRouter(tags=["checkin-settlement"])

_CAPTURE_ROLES  = frozenset({"admin", "manager", "ops", "worker", "checkin", "checkout"})
_WRITE_ROLES    = frozenset({"admin", "ops", "worker", "checkin"})
_CORRECT_ROLES  = frozenset({"admin", "ops", "checkin"})
_ADMIN_ROLES    = frozenset({"admin", "manager"})


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


# ---------------------------------------------------------------------------
# Audit helper
# ---------------------------------------------------------------------------

def _audit(db: Any, tenant_id: str, actor_id: str, action: str,
           entity_type: str, entity_id: str, details: dict) -> None:
    try:
        db.table("admin_audit_log").insert({
            "tenant_id":    tenant_id,
            "actor_id":     actor_id,
            "action":       action,
            "entity_type":  entity_type,
            "entity_id":    entity_id,
            "details":      details,
            "performed_at": _now_iso(),
        }).execute()
    except Exception as exc:
        logger.warning("checkin_settlement: audit write failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_property_id(db: Any, tenant_id: str, booking_id: str) -> Optional[str]:
    try:
        res = (
            db.table("booking_state")
            .select("property_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0].get("property_id") if rows else None
    except Exception:
        return None


def _get_charge_rule(db: Any, tenant_id: str, property_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("property_charge_rules")
            .select("deposit_enabled, deposit_amount, deposit_currency, "
                    "electricity_enabled, electricity_rate_kwh")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------

def _serialize_deposit(row: dict) -> dict:
    return {
        "id":             row.get("id"),
        "booking_id":     row.get("booking_id"),
        "amount":         row.get("amount"),
        "currency":       row.get("currency", "THB"),
        "status":         row.get("status"),
        "collected_by":   row.get("collected_by"),
        "collected_at":   row.get("collected_at"),
        "notes":          row.get("notes"),
        "created_at":     row.get("created_at"),
    }


def _serialize_meter_reading(row: dict) -> dict:
    return {
        "id":              row.get("id"),
        "booking_id":      row.get("booking_id"),
        "property_id":     row.get("property_id"),
        "reading_type":    row.get("reading_type", "opening"),
        "meter_value":     row.get("meter_value"),
        "meter_unit":      row.get("meter_unit", "kWh"),
        "meter_photo_url": row.get("meter_photo_url"),
        "recorded_by":     row.get("recorded_by"),
        "recorded_at":     row.get("recorded_at"),
        "supercedes_id":   row.get("supercedes_id"),
        "notes":           row.get("notes"),
        "created_at":      row.get("created_at"),
    }


# ===========================================================================
# Phase 957 + 963 + 964 — POST check-in settlement (HARD WIZARD)
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/checkin-settlement",
    summary="Capture check-in deposit + opening meter (hard-enforced, Phase 963-964)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_checkin_settlement(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Hard-enforced check-in settlement capture (Phase 963 correction).

    If the property's charge rule requires deposit or electricity capture,
    the worker MUST provide them. Omitting a required step returns 400.

    **Admin override:** set `force_override=true` + `override_reason` in the body
    to bypass required steps. Logged to admin_audit_log as an explicit exception.

    **Deposit fields (required if deposit_enabled=true):**
    - `deposit_collected` (bool) — MUST be true if deposit required
    - `deposit_amount` (number) — actual amount collected
    - `deposit_currency` (string, optional, default from charge rule or THB)
    - `deposit_notes` (string, optional)

    **Electricity fields (required if electricity_enabled=true):**
    - `meter_reading` (number ≥ 0)
    - `meter_photo_url` (string, optional)
    - `meter_notes` (string, optional)

    **Writes to (Phase 964):**
    - `cash_deposits` — the REAL financial deposit record, status='collected'
    - `checkin_deposit_records` — secondary operational trail
    - `electricity_meter_readings` — opening reading

    Auth: checkin, ops, worker, admin.
    """
    role = identity.get("role", "")
    if role not in _WRITE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot write check-in settlement capture."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    db = client or _get_db()

    # Resolve property_id
    property_id = _get_property_id(db, tenant_id, booking_id)
    if not property_id:
        return make_error_response(
            status_code=404, code=ErrorCode.NOT_FOUND,
            extra={"detail": f"Booking '{booking_id}' not found."},
        )

    # Load charge rule for hard validation
    charge_rule = _get_charge_rule(db, tenant_id, property_id)
    force_override  = bool(body.get("force_override", False))
    override_reason = (body.get("override_reason") or "").strip()

    now = _now_iso()
    cash_deposit_id: Optional[str]  = None
    deposit_record_id: Optional[str] = None
    meter_reading_id: Optional[str]  = None

    # ── PHASE 963: Hard validation ────────────────────────────────────────
    deposit_collected = bool(body.get("deposit_collected", False))
    deposit_amount    = body.get("deposit_amount")
    meter_value       = body.get("meter_reading")
    # OCR linkage: present when worker used OCR capture for meter (Phase 986)
    meter_ocr_result_id = body.get("ocr_result_id") or None

    if charge_rule:
        # Deposit required?
        if charge_rule.get("deposit_enabled"):
            if not deposit_collected:
                if force_override and override_reason:
                    _audit(db, tenant_id, actor_id, "checkin_override_deposit_skipped",
                           "booking", booking_id,
                           {"override_reason": override_reason, "property_id": property_id})
                else:
                    return make_error_response(
                        status_code=400, code=ErrorCode.VALIDATION_ERROR,
                        extra={"detail":
                               "This property requires deposit collection at check-in "
                               "(deposit_enabled=true). Set deposit_collected=true with "
                               "a valid deposit_amount, or provide force_override=true "
                               "with override_reason to bypass."},
                    )
            elif deposit_amount is None:
                return make_error_response(
                    status_code=400, code=ErrorCode.VALIDATION_ERROR,
                    extra={"detail": "deposit_amount is required when deposit_collected=true."},
                )

        # Electricity required?
        if charge_rule.get("electricity_enabled"):
            if meter_value is None:
                if force_override and override_reason:
                    _audit(db, tenant_id, actor_id, "checkin_override_meter_skipped",
                           "booking", booking_id,
                           {"override_reason": override_reason, "property_id": property_id})
                else:
                    return make_error_response(
                        status_code=400, code=ErrorCode.VALIDATION_ERROR,
                        extra={"detail":
                               "This property requires opening electricity meter reading "
                               "at check-in (electricity_enabled=true). Provide meter_reading, "
                               "or provide force_override=true with override_reason to bypass."},
                    )

    # ── Deposit capture (Phase 964: direct cash_deposits write) ───────────
    if deposit_collected and deposit_amount is not None:
        try:
            deposit_amount = float(deposit_amount)
            if deposit_amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "deposit_amount must be a positive number."},
            )

        currency = (
            body.get("deposit_currency")
            or (charge_rule or {}).get("deposit_currency", "THB")
        ).upper()

        # 1. Write to cash_deposits — the REAL deposit (Phase 964)
        cash_deposit_id = hashlib.sha256(
            f"DEP:{booking_id}:{now}".encode()
        ).hexdigest()[:16]
        cash_deposit_row = {
            "id":           cash_deposit_id,
            "booking_id":   booking_id,
            "tenant_id":    tenant_id,
            "amount":       deposit_amount,
            "currency":     currency,
            "status":       "collected",
            "collected_by": actor_id,
            "collected_at": now,
            "notes":        body.get("deposit_notes") or None,
            "refund_amount": deposit_amount,  # Initially full refund potential
            "created_at":   now,
        }
        try:
            db.table("cash_deposits").insert(cash_deposit_row).execute()
        except Exception as exc:
            logger.exception("checkin-settlement cash_deposits insert error: %s", exc)
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

        # 2. Write to checkin_deposit_records — secondary operational trail
        deposit_record_id = str(uuid.uuid4())
        checkin_dep_row = {
            "id":              deposit_record_id,
            "tenant_id":       tenant_id,
            "booking_id":      booking_id,
            "property_id":     property_id,
            "amount":          deposit_amount,
            "currency":        currency,
            "collected_by":    actor_id,
            "collected_at":    now,
            "cash_deposit_id": cash_deposit_id,  # Linked from the start
            "notes":           body.get("deposit_notes") or None,
        }
        try:
            db.table("checkin_deposit_records").insert(checkin_dep_row).execute()
        except Exception as exc:
            # Non-blocking: the cash_deposits write is the primary record
            logger.warning("checkin-settlement secondary trail write failed: %s", exc)

        _audit(db, tenant_id, actor_id, "deposit_collected_at_checkin",
               "cash_deposit", cash_deposit_id,
               {"booking_id": booking_id, "amount": deposit_amount,
                "currency": currency, "property_id": property_id})

    # ── Electricity meter capture ─────────────────────────────────────────
    if meter_value is not None:
        try:
            meter_value = float(meter_value)
            if meter_value < 0:
                raise ValueError
        except (TypeError, ValueError):
            return make_error_response(
                status_code=400, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "meter_reading must be a non-negative number (kWh)."},
            )

        meter_reading_id = str(uuid.uuid4())
        meter_row = {
            "id":              meter_reading_id,
            "tenant_id":       tenant_id,
            "booking_id":      booking_id,
            "property_id":     property_id,
            "reading_type":    "opening",
            "meter_value":     meter_value,
            "meter_unit":      "kWh",
            "meter_photo_url": body.get("meter_photo_url") or None,
            "recorded_by":     actor_id,
            "recorded_at":     now,
            "notes":           body.get("meter_notes") or None,
            "ocr_result_id":   meter_ocr_result_id,  # None if manually entered
        }
        try:
            db.table("electricity_meter_readings").insert(meter_row).execute()
            _audit(db, tenant_id, actor_id, "meter_opening_recorded",
                   "electricity_meter_reading", meter_reading_id,
                   {"booking_id": booking_id, "meter_value": meter_value,
                    "has_photo": bool(body.get("meter_photo_url")),
                    "property_id": property_id})
        except Exception as exc:
            logger.exception("checkin-settlement meter insert error: %s", exc)
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    return JSONResponse(status_code=201, content={
        "booking_id":        booking_id,
        "property_id":       property_id,
        "cash_deposit_id":   cash_deposit_id,
        "deposit_record_id": deposit_record_id,
        "meter_reading_id":  meter_reading_id,
        "force_override":    force_override if force_override else None,
    })


# ===========================================================================
# Phase 957 — Worker: GET /worker/bookings/{booking_id}/checkin-settlement
# ===========================================================================

@router.get(
    "/worker/bookings/{booking_id}/checkin-settlement",
    summary="Read check-in settlement capture state for a booking (Phase 957)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_checkin_settlement(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the current check-in settlement capture state for a booking:
    - The cash_deposits record (the REAL deposit — Phase 964)
    - The active opening meter reading (most recent)

    No writes. Readable by checkin, ops, worker, admin, manager.
    """
    role = identity.get("role", "")
    if role not in _CAPTURE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot read check-in settlement capture."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        # Cash deposit (the real record — Phase 964)
        dep_res = (
            db.table("cash_deposits")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        deposit_record = (_serialize_deposit(dep_res.data[0])
                          if dep_res.data else None)

        # Active opening meter reading (most recent, type=opening)
        meter_res = (
            db.table("electricity_meter_readings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("reading_type", "opening")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        meter_reading = (_serialize_meter_reading(meter_res.data[0])
                         if meter_res.data else None)

        return JSONResponse(status_code=200, content={
            "booking_id":     booking_id,
            "deposit_record": deposit_record,
            "meter_reading":  meter_reading,
        })

    except Exception as exc:
        logger.exception("GET checkin-settlement %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 957 — Worker: POST meter reading correction
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/meter-reading/correction",
    summary="Correct an opening meter reading (append-only, Phase 957)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def correct_meter_reading(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Submit a corrected opening meter reading. The original row is NOT modified.
    A new row is created with `supercedes_id` pointing to the row being corrected.

    **Required:** `meter_reading` (number), `supercedes_id` (UUID of the row to correct)
    **Optional:** `meter_photo_url`, `notes`

    Auth: checkin, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _CORRECT_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot submit meter reading corrections."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    meter_value   = body.get("meter_reading")
    supercedes_id = body.get("supercedes_id")

    if meter_value is None or not supercedes_id:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "meter_reading and supercedes_id are required."},
        )
    try:
        meter_value = float(meter_value)
        if meter_value < 0:
            raise ValueError
    except (TypeError, ValueError):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "meter_reading must be a non-negative number."},
        )

    try:
        db = client or _get_db()

        property_id = _get_property_id(db, tenant_id, booking_id)
        if not property_id:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        # Verify the superceded row exists and belongs to this booking
        orig_res = (
            db.table("electricity_meter_readings")
            .select("id, reading_type")
            .eq("id", supercedes_id)
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .limit(1)
            .execute()
        )
        if not (orig_res.data or []):
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Meter reading '{supercedes_id}' not found for this booking."},
            )

        now = _now_iso()
        correction_id = str(uuid.uuid4())
        correction_row = {
            "id":              correction_id,
            "tenant_id":       tenant_id,
            "booking_id":      booking_id,
            "property_id":     property_id,
            "reading_type":    orig_res.data[0].get("reading_type", "opening"),
            "meter_value":     meter_value,
            "meter_unit":      "kWh",
            "meter_photo_url": body.get("meter_photo_url") or None,
            "recorded_by":     actor_id,
            "recorded_at":     now,
            "supercedes_id":   supercedes_id,
            "notes":           body.get("notes") or None,
        }
        db.table("electricity_meter_readings").insert(correction_row).execute()

        _audit(db, tenant_id, actor_id, "meter_reading_corrected",
               "electricity_meter_reading", correction_id,
               {"booking_id": booking_id, "corrected_value": meter_value,
                "supercedes_id": supercedes_id})

        return JSONResponse(status_code=201,
                            content=_serialize_meter_reading(correction_row))

    except Exception as exc:
        logger.exception("POST meter-correction %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 958 — Admin: GET /admin/bookings/{booking_id}/settlement-capture
# ===========================================================================

@router.get(
    "/admin/bookings/{booking_id}/settlement-capture",
    summary="Full settlement capture view for admin (Phase 958)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def admin_get_settlement_capture(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Full operational view of the check-in settlement capture for a booking.

    Returns:
    - The property's charge rule
    - The cash_deposits record (the real deposit — Phase 964)
    - All opening meter readings (full correction history)
    - The active (latest) opening reading

    Admin and manager only.
    """
    role = identity.get("role", "")
    if role not in _ADMIN_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Requires admin or manager role."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        property_id = _get_property_id(db, tenant_id, booking_id)
        if not property_id:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        # Charge rule
        charge_rule = _get_charge_rule(db, tenant_id, property_id)

        # Cash deposit (the real deposit — Phase 964)
        dep_res = (
            db.table("cash_deposits")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("created_at", desc=True)
            .execute()
        )
        deposit_records = [_serialize_deposit(r) for r in (dep_res.data or [])]

        # All opening meter readings (full history)
        meter_res = (
            db.table("electricity_meter_readings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("reading_type", "opening")
            .order("created_at", desc=False)
            .execute()
        )
        meter_readings = [_serialize_meter_reading(r) for r in (meter_res.data or [])]
        active_meter = meter_readings[-1] if meter_readings else None

        # Completeness assessment
        missing = []
        if charge_rule:
            if charge_rule.get("deposit_enabled") and not deposit_records:
                missing.append("deposit (property has deposit_enabled=true)")
            if charge_rule.get("electricity_enabled") and not meter_readings:
                missing.append("meter_reading (property has electricity_enabled=true)")

        return JSONResponse(status_code=200, content={
            "booking_id":      booking_id,
            "property_id":     property_id,
            "charge_rule":     charge_rule,
            "deposit_records": deposit_records,
            "meter_readings":  {
                "history": meter_readings,
                "active":  active_meter,
            },
            "missing_captures": missing,
        })

    except Exception as exc:
        logger.exception("GET settlement-capture %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
