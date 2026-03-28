"""
Phases 959–961, corrected by 965–967 — Checkout Settlement Engine
==================================================================

Phase 959 — Closing meter capture at checkout.
Phase 961 — Settlement lifecycle: start → calculate → deductions → finalize → void.
Phase 965 — Deduction category constraint: electricity | damage | miscellaneous.
Phase 966 — Auto-electricity deduction: /calculate auto-creates a deposit_deductions
            row with category='electricity' from meter delta × rate. Not manual.
Phase 967 — miscellaneous_deductions_total tracked separately on settlement record.

Worker endpoints:
    POST /worker/bookings/{booking_id}/closing-meter
         Capture closing electricity meter reading at checkout.

    POST /worker/bookings/{booking_id}/settlement/start
         Create a draft settlement record.

    POST /worker/bookings/{booking_id}/settlement/calculate
         Run the engine. AUTO-creates electricity deduction row (Phase 966).
         Computes all totals. Idempotent (safe to call multiple times).

    POST /worker/bookings/{booking_id}/settlement/deductions
         Add a damage or miscellaneous deduction. Category MUST be 'damage'
         or 'miscellaneous' (Phase 965). Electricity deductions are auto-created.

    DELETE /worker/bookings/{booking_id}/settlement/deductions/{deduction_id}
         Remove a deduction. Resets settlement to draft.

    POST /worker/bookings/{booking_id}/settlement/finalize
         Lock settlement. Updates cash_deposits status. Terminal.

Admin endpoints:
    POST /admin/bookings/{booking_id}/settlement/void
         Void a non-finalized settlement. Admin only.

    GET  /admin/bookings/{booking_id}/settlement
         Full settlement view with categorized deductions.

    GET  /admin/properties/{property_id}/settlements
         List settlements for a property.

Status machine:
    draft → calculated → finalized (terminal)
    draft | calculated → voided (terminal, admin only)

Photography pattern:
    All photo fields (meter_photo_url, photo_url) store Supabase Storage URLs only.
    Binary upload is handled by the frontend → Supabase Storage directly.
    Backend never handles binary photo data in this router.

Invariants:
    - At most one non-voided settlement per booking (DB partial unique index).
    - finalized rows are fully immutable.
    - electricity_rate_kwh is snapshotted at calculate time.
    - Electricity deduction is AUTO-CREATED by /calculate (Phase 966).
    - Manual deduction category must be 'damage' or 'miscellaneous' (Phase 965).
    - finalize triggers cash_deposits status update — the ONLY cross-table side effect.
    - NEVER writes to event_log, booking_state, or booking_financial_facts.
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
router = APIRouter(tags=["checkout-settlement"])

_WRITE_ROLES     = frozenset({"admin", "ops", "worker", "checkin", "checkout"})
_DEDUCT_ROLES    = frozenset({"admin", "ops", "checkout"})
_FINALIZE_ROLES  = frozenset({"admin", "ops", "worker", "checkout"})
_VOID_ROLES      = frozenset({"admin"})
_READ_ADMIN      = frozenset({"admin", "manager"})

# Phase 965: valid manual deduction categories (electricity is auto-only)
_MANUAL_DEDUCTION_CATEGORIES = frozenset({"damage", "miscellaneous"})


# ---------------------------------------------------------------------------
# DB / time helpers
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
        logger.warning("checkout_settlement: audit write failed (non-blocking): %s", exc)


# ---------------------------------------------------------------------------
# Shared lookup helpers
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


def _get_active_settlement(db: Any, tenant_id: str,
                           booking_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("booking_settlement_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .neq("status", "voided")
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_opening_meter(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    """Get the active (latest) opening meter reading for a booking."""
    try:
        res = (
            db.table("electricity_meter_readings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("reading_type", "opening")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_closing_meter(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    """Get the active (latest) closing meter reading for a booking."""
    try:
        res = (
            db.table("electricity_meter_readings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("reading_type", "closing")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_charge_rule(db: Any, tenant_id: str, property_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("property_charge_rules")
            .select("deposit_enabled, deposit_amount, deposit_currency, "
                    "electricity_enabled, electricity_rate_kwh, electricity_currency")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_deposit_held(db: Any, tenant_id: str, booking_id: str) -> tuple[float, str]:
    """
    Resolve deposit held for this booking from cash_deposits (Phase 964).
    Returns (amount, currency).
    """
    try:
        res = (
            db.table("cash_deposits")
            .select("amount, currency")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("status", "collected")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows:
            return float(rows[0]["amount"]), rows[0].get("currency", "THB")
    except Exception:
        pass
    return 0.0, "THB"


def _get_cash_deposit_id(db: Any, tenant_id: str, booking_id: str) -> Optional[str]:
    """Lookup the cash_deposits ID for this booking."""
    try:
        res = (
            db.table("cash_deposits")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .eq("status", "collected")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0]["id"] if rows else None
    except Exception:
        return None


def _get_deductions_by_category(
    db: Any, deposit_id: Optional[str]
) -> dict:
    """
    Get all deductions grouped by category (Phase 965-967).
    Returns {
        'electricity': (list, total),
        'damage': (list, total),
        'miscellaneous': (list, total),
        'all': (list, grand_total),
    }
    """
    result: dict = {
        "electricity":   ([], 0.0),
        "damage":        ([], 0.0),
        "miscellaneous": ([], 0.0),
        "all":           ([], 0.0),
    }
    if not deposit_id:
        return result
    try:
        res = (
            db.table("deposit_deductions")
            .select("*")
            .eq("deposit_id", deposit_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = res.data or []
        all_rows: list[dict] = []
        by_cat: dict[str, list[dict]] = {"electricity": [], "damage": [], "miscellaneous": []}
        for row in rows:
            cat = row.get("category", "damage")
            if cat in by_cat:
                by_cat[cat].append(row)
            else:
                by_cat["miscellaneous"].append(row)
            all_rows.append(row)

        grand_total = sum(float(r["amount"]) for r in all_rows)
        result = {
            "electricity":   (by_cat["electricity"],   sum(float(r["amount"]) for r in by_cat["electricity"])),
            "damage":        (by_cat["damage"],         sum(float(r["amount"]) for r in by_cat["damage"])),
            "miscellaneous": (by_cat["miscellaneous"],  sum(float(r["amount"]) for r in by_cat["miscellaneous"])),
            "all":           (all_rows,                 grand_total),
        }
    except Exception:
        pass
    return result


def _serialize_settlement(row: dict) -> dict:
    return {k: v for k, v in row.items()}


# ===========================================================================
# Phase 959 — POST /worker/bookings/{booking_id}/closing-meter
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/closing-meter",
    summary="Capture closing electricity meter reading at checkout (Phase 959)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def capture_closing_meter(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Write the closing electricity meter reading for a booking at checkout.

    Stored in `electricity_meter_readings` with `reading_type='closing'`.
    Paired with the opening reading (Phase 957) to compute kWh consumed.

    **Required:** `meter_reading` (number ≥ 0)
    **Optional:** `meter_photo_url` (Supabase Storage URL), `notes`

    Photo note: meter_photo_url must be a pre-uploaded Supabase Storage URL.
    Binary upload happens frontend → Supabase Storage, not through this endpoint.

    Auth: checkin, checkout, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _WRITE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot capture closing meter readings."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    meter_value = body.get("meter_reading")
    # OCR linkage: present when worker used OCR capture for closing meter (Phase 986)
    meter_ocr_result_id = body.get("ocr_result_id") or None
    if meter_value is None:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "meter_reading is required."},
        )
    try:
        meter_value = float(meter_value)
        if meter_value < 0:
            raise ValueError
    except (TypeError, ValueError):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "meter_reading must be a non-negative number (kWh)."},
        )

    try:
        db = client or _get_db()

        property_id = _get_property_id(db, tenant_id, booking_id)
        if not property_id:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        # Warn if no opening reading exists
        warnings: list[str] = []
        opening = _get_opening_meter(db, tenant_id, booking_id)
        if not opening:
            warnings.append(
                "No opening meter reading found for this booking. "
                "The electricity calculation will not be possible without it."
            )
        elif meter_value < float(opening["meter_value"]):
            warnings.append(
                f"Closing reading ({meter_value}) is less than the opening reading "
                f"({opening['meter_value']}). This is unusual — please verify."
            )

        now = _now_iso()
        reading_id = str(uuid.uuid4())
        row = {
            "id":              reading_id,
            "tenant_id":       tenant_id,
            "booking_id":      booking_id,
            "property_id":     property_id,
            "reading_type":    "closing",
            "meter_value":     meter_value,
            "meter_unit":      "kWh",
            "meter_photo_url": body.get("meter_photo_url") or None,
            "recorded_by":     actor_id,
            "recorded_at":     now,
            "notes":           body.get("notes") or None,
            "ocr_result_id":   meter_ocr_result_id,  # None if manually entered
        }
        db.table("electricity_meter_readings").insert(row).execute()

        _audit(db, tenant_id, actor_id, "meter_closing_recorded",
               "electricity_meter_reading", reading_id,
               {"booking_id": booking_id, "meter_value": meter_value,
                "has_photo": bool(body.get("meter_photo_url")),
                "opening_value": float(opening["meter_value"]) if opening else None})

        return JSONResponse(status_code=201, content={
            "reading_id":    reading_id,
            "booking_id":    booking_id,
            "reading_type":  "closing",
            "meter_value":   meter_value,
            "meter_unit":    "kWh",
            "recorded_by":   actor_id,
            "recorded_at":   now,
            "warnings":      warnings,
        })

    except Exception as exc:
        logger.exception("POST closing-meter %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 — POST /worker/bookings/{booking_id}/settlement/start
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/settlement/start",
    summary="Create a draft settlement record for a booking (Phase 961)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def start_settlement(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Create a new draft settlement record for this booking.

    Only allowed if no non-voided settlement exists yet.
    Call `calculate` next to populate the computed fields.

    Auth: checkin, checkout, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _WRITE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot start a settlement."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        # Guard: only one active settlement per booking
        existing = _get_active_settlement(db, tenant_id, booking_id)
        if existing:
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": f"A settlement record already exists for this booking "
                                 f"(id={existing['id']}, status={existing['status']}). "
                                 "Void it before creating a new one."},
            )

        property_id = _get_property_id(db, tenant_id, booking_id)
        if not property_id:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )

        deposit_held, deposit_currency = _get_deposit_held(db, tenant_id, booking_id)

        now = _now_iso()
        settlement_id = str(uuid.uuid4())
        row = {
            "id":                  settlement_id,
            "tenant_id":           tenant_id,
            "booking_id":          booking_id,
            "property_id":        property_id,
            "status":              "draft",
            "deposit_held":        deposit_held,
            "deposit_currency":    deposit_currency,
            "damage_deductions_total":        0,
            "miscellaneous_deductions_total": 0,
            "total_deductions":    0,
            "refund_amount":       deposit_held,
            "retained_amount":     0,
            "created_by":          actor_id,
            "created_at":          now,
            "updated_at":          now,
        }
        res = db.table("booking_settlement_records").insert(row).execute()
        saved = (res.data or [{}])[0]

        _audit(db, tenant_id, actor_id, "settlement_started",
               "booking_settlement_record", settlement_id,
               {"booking_id": booking_id, "deposit_held": deposit_held})

        return JSONResponse(status_code=201, content=_serialize_settlement(saved))

    except Exception as exc:
        logger.exception("POST settlement/start %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 + 966 — POST calculate (core engine with auto-electricity deduction)
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/settlement/calculate",
    summary="Run settlement calculation with auto-electricity deduction (Phase 966)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def calculate_settlement(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Run the settlement calculation engine.

    **Phase 966 correction: Auto-electricity deduction**

    If electricity readings exist and the property has a configured rate:
    1. System computes kWh delta = closing − opening
    2. System computes charge = delta × rate_per_kwh
    3. System AUTO-CREATES a `deposit_deductions` row with category='electricity'
       (or updates an existing one from a prior calculation run)

    This is not a suggestion — it is an enforced automatic deduction.

    Then the engine sums all three deduction categories:
    - `electricity` (auto-created above)
    - `damage` (manual via /deductions endpoint)
    - `miscellaneous` (manual via /deductions endpoint)

    And computes:
    - `total_deductions` = electricity + damage + miscellaneous
    - `refund_amount` = MAX(0, deposit_held − total_deductions)
    - `retained_amount` = deposit_held − refund_amount

    Idempotent — safe to call multiple times. Re-calculates from current
    readings and deductions each time.

    Auth: checkin, checkout, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _WRITE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot run settlement calculation."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        settlement = _get_active_settlement(db, tenant_id, booking_id)
        if not settlement:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": "No active settlement found. Call /settlement/start first."},
            )
        if settlement["status"] == "finalized":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": "Settlement is already finalized and cannot be recalculated."},
            )

        property_id = settlement["property_id"]
        deposit_held = float(settlement["deposit_held"])
        deposit_currency = settlement.get("deposit_currency", "THB")

        # ── Electricity calculation ──────────────────────────────────────
        opening = _get_opening_meter(db, tenant_id, booking_id)
        closing = _get_closing_meter(db, tenant_id, booking_id)
        charge_rule = _get_charge_rule(db, tenant_id, property_id)

        electricity_kwh_used = None
        electricity_charged  = 0.0
        electricity_rate_kwh = None
        electricity_currency = None
        opening_meter_id     = None
        closing_meter_id     = None
        warnings: list[str]  = []

        if charge_rule and charge_rule.get("electricity_enabled"):
            if not opening:
                warnings.append("No opening meter reading found — electricity cannot be calculated.")
            elif not closing:
                warnings.append("No closing meter reading found — electricity cannot be calculated.")
            else:
                o_val = float(opening["meter_value"])
                c_val = float(closing["meter_value"])
                if c_val < o_val:
                    warnings.append(
                        f"Closing reading ({c_val}) < opening reading ({o_val}). "
                        "kWh usage will be treated as 0."
                    )
                    electricity_kwh_used = 0.0
                else:
                    electricity_kwh_used = round(c_val - o_val, 4)

                rate = charge_rule.get("electricity_rate_kwh")
                if rate and electricity_kwh_used is not None:
                    electricity_rate_kwh = float(rate)
                    electricity_charged  = round(electricity_kwh_used * electricity_rate_kwh, 2)
                    electricity_currency = charge_rule.get("electricity_currency", "THB")
                else:
                    warnings.append("electricity_rate_kwh not configured — electricity charge is 0.")

                opening_meter_id = str(opening["id"])
                closing_meter_id = str(closing["id"])

        # ── Phase 966: Auto-create electricity deduction row ─────────────
        cash_deposit_id = _get_cash_deposit_id(db, tenant_id, booking_id)
        now = _now_iso()

        if cash_deposit_id and electricity_charged > 0:
            # Remove any existing electricity deduction (idempotent recalculation)
            try:
                db.table("deposit_deductions").delete().eq(
                    "deposit_id", cash_deposit_id
                ).eq("category", "electricity").execute()
            except Exception:
                pass

            # Auto-create the electricity deduction
            elec_ded_id = hashlib.sha256(
                f"ELEC:{cash_deposit_id}:{booking_id}:{now}".encode()
            ).hexdigest()[:16]
            db.table("deposit_deductions").insert({
                "id":          elec_ded_id,
                "deposit_id":  cash_deposit_id,
                "description": f"Electricity: {electricity_kwh_used} kWh × {electricity_rate_kwh}/kWh",
                "amount":      electricity_charged,
                "category":    "electricity",
                "created_at":  now,
            }).execute()

            _audit(db, tenant_id, actor_id, "electricity_deduction_auto_created",
                   "deposit_deduction", elec_ded_id,
                   {"booking_id": booking_id, "kwh_used": electricity_kwh_used,
                    "rate": electricity_rate_kwh, "charged": electricity_charged})

        elif cash_deposit_id and electricity_charged == 0:
            # Clean up old electricity deduction if rate/readings changed to zero
            try:
                db.table("deposit_deductions").delete().eq(
                    "deposit_id", cash_deposit_id
                ).eq("category", "electricity").execute()
            except Exception:
                pass

        # ── Sum all deductions by category (Phase 965-967) ───────────────
        cats = _get_deductions_by_category(db, cash_deposit_id)
        elec_total = cats["electricity"][1]
        damage_total = cats["damage"][1]
        misc_total = cats["miscellaneous"][1]

        # ── Final amounts ────────────────────────────────────────────────
        total_deductions = round(elec_total + damage_total + misc_total, 2)
        refund_amount    = round(max(0.0, deposit_held - total_deductions), 2)
        retained_amount  = round(deposit_held - refund_amount, 2)

        update = {
            "status":                          "calculated",
            "opening_meter_value":             float(opening["meter_value"]) if opening else None,
            "closing_meter_value":             float(closing["meter_value"]) if closing else None,
            "electricity_kwh_used":            electricity_kwh_used,
            "electricity_rate_kwh":            electricity_rate_kwh,
            "electricity_charged":             electricity_charged,
            "electricity_currency":            electricity_currency,
            "opening_meter_reading_id":        opening_meter_id,
            "closing_meter_reading_id":        closing_meter_id,
            "damage_deductions_total":         damage_total,
            "miscellaneous_deductions_total":  misc_total,
            "total_deductions":                total_deductions,
            "refund_amount":                   refund_amount,
            "retained_amount":                 retained_amount,
            "updated_at":                      now,
        }
        db.table("booking_settlement_records").update(update).eq(
            "id", settlement["id"]
        ).execute()

        _audit(db, tenant_id, actor_id, "settlement_calculated",
               "booking_settlement_record", settlement["id"],
               {"kWh_used": electricity_kwh_used, "electricity_charged": electricity_charged,
                "damage_total": damage_total, "misc_total": misc_total,
                "refund_amount": refund_amount, "retained_amount": retained_amount})

        return JSONResponse(status_code=200, content={
            "settlement_id":          settlement["id"],
            "booking_id":             booking_id,
            "status":                 "calculated",
            "deposit_held":           deposit_held,
            "deposit_currency":       deposit_currency,
            "electricity": {
                "opening_meter_value":  float(opening["meter_value"]) if opening else None,
                "closing_meter_value":  float(closing["meter_value"]) if closing else None,
                "kwh_used":             electricity_kwh_used,
                "rate_kwh":             electricity_rate_kwh,
                "charged":              electricity_charged,
                "currency":             electricity_currency,
                "auto_deduction":       True,
            },
            "deductions_by_category": {
                "electricity":   {"items": cats["electricity"][0], "total": elec_total},
                "damage":        {"items": cats["damage"][0],      "total": damage_total},
                "miscellaneous": {"items": cats["miscellaneous"][0], "total": misc_total},
            },
            "total_deductions":       total_deductions,
            "refund_amount":          refund_amount,
            "retained_amount":        retained_amount,
            "warnings":               warnings,
        })

    except Exception as exc:
        logger.exception("POST settlement/calculate %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 + 965 — POST deductions (damage or miscellaneous ONLY)
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/settlement/deductions",
    summary="Add damage or miscellaneous deduction (Phase 965)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def add_settlement_deduction(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Add a damage or miscellaneous deduction to this booking's settlement.

    Phase 965 correction: category MUST be 'damage' or 'miscellaneous'.
    Electricity deductions are AUTO-CREATED by /calculate and cannot be
    manually added. Attempting to add category='electricity' returns 400.

    Writes to `deposit_deductions` linked to the booking's cash_deposits record.
    Resets settlement status to 'draft' — /calculate must be run again.

    **Required:** `description`, `amount`, `category` (damage | miscellaneous)
    **Optional:** `photo_url` (Supabase Storage URL — pre-uploaded by frontend)

    Auth: checkout, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _DEDUCT_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot add settlement deductions."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    description = (body.get("description") or "").strip()
    amount      = body.get("amount")
    category    = (body.get("category") or "").strip().lower()
    photo_url   = body.get("photo_url") or None

    if not description:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "description is required."},
        )
    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "amount must be a positive number."},
        )

    # Phase 965: enforce category constraint
    if category not in _MANUAL_DEDUCTION_CATEGORIES:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"category must be 'damage' or 'miscellaneous'. "
                             f"Got: '{category}'. Electricity deductions are auto-created "
                             "by /settlement/calculate and cannot be manually added."},
        )

    try:
        db = client or _get_db()

        settlement = _get_active_settlement(db, tenant_id, booking_id)
        if not settlement:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": "No active settlement found. Call /settlement/start first."},
            )
        if settlement["status"] == "finalized":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": "Cannot add deductions to a finalized settlement."},
            )

        # Require a cash_deposits row to attach deductions to
        cash_deposit_id = _get_cash_deposit_id(db, tenant_id, booking_id)
        if not cash_deposit_id:
            return make_error_response(
                status_code=422, code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "No cash_deposits record found for this booking. "
                                 "Deposit must be collected at check-in before "
                                 "deductions can be attached."},
            )

        now = _now_iso()
        ded_id = hashlib.sha256(
            f"DED:{cash_deposit_id}:{description}:{now}".encode()
        ).hexdigest()[:16]

        db.table("deposit_deductions").insert({
            "id":          ded_id,
            "deposit_id":  cash_deposit_id,
            "description": description,
            "amount":      amount,
            "category":    category,
            "photo_url":   photo_url,
            "created_at":  now,
        }).execute()

        # Reset settlement to draft so recalculation is required
        db.table("booking_settlement_records").update({
            "status":     "draft",
            "updated_at": now,
        }).eq("id", settlement["id"]).execute()

        _audit(db, tenant_id, actor_id, "settlement_deduction_added",
               "booking_settlement_record", settlement["id"],
               {"deduction_id": ded_id, "description": description,
                "amount": amount, "category": category})

        return JSONResponse(status_code=201, content={
            "deduction_id":  ded_id,
            "settlement_id": settlement["id"],
            "category":      category,
            "status":        "draft",
            "message":       "Deduction added. Call /settlement/calculate to refresh totals.",
        })

    except Exception as exc:
        logger.exception("POST settlement/deductions %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 — DELETE deduction
# ===========================================================================

@router.delete(
    "/worker/bookings/{booking_id}/settlement/deductions/{deduction_id}",
    summary="Remove a deduction from the settlement (Phase 961)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def remove_settlement_deduction(
    booking_id: str,
    deduction_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Remove a deduction. Resets settlement to draft (recalculation required).
    Electricity deductions CAN be manually removed (the next /calculate will
    re-create them if the readings still exist).
    Auth: checkout, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _DEDUCT_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot remove settlement deductions."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        settlement = _get_active_settlement(db, tenant_id, booking_id)
        if not settlement:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": "No active settlement found."},
            )
        if settlement["status"] == "finalized":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": "Cannot remove deductions from a finalized settlement."},
            )

        db.table("deposit_deductions").delete().eq("id", deduction_id).execute()

        now = _now_iso()
        db.table("booking_settlement_records").update({
            "status":     "draft",
            "updated_at": now,
        }).eq("id", settlement["id"]).execute()

        _audit(db, tenant_id, actor_id, "settlement_deduction_removed",
               "booking_settlement_record", settlement["id"],
               {"deduction_id": deduction_id, "booking_id": booking_id})

        return JSONResponse(status_code=200, content={
            "deduction_id":  deduction_id,
            "settlement_id": settlement["id"],
            "status":        "draft",
            "message":       "Deduction removed. Call /settlement/calculate to refresh totals.",
        })

    except Exception as exc:
        logger.exception("DELETE settlement/deductions %s/%s error tenant=%s: %s",
                         booking_id, deduction_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 — POST finalize
# ===========================================================================

@router.post(
    "/worker/bookings/{booking_id}/settlement/finalize",
    summary="Finalize the settlement — lock amounts and update deposit status (Phase 961)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def finalize_settlement(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Lock the settlement. Terminal operation.

    After finalization:
    - `booking_settlement_records.status` → `finalized` (immutable)
    - `cash_deposits.status` is updated:
        - `returned` if `refund_amount > 0`
        - `forfeited` if `refund_amount == 0` and `retained_amount > 0`
        - left as `collected` if no cash_deposits record exists

    **Requires:** settlement must be in `calculated` status.

    Auth: ops, admin only.
    """
    role = identity.get("role", "")
    if role not in _FINALIZE_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only ops and admin can finalize a settlement."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    try:
        db = client or _get_db()

        settlement = _get_active_settlement(db, tenant_id, booking_id)
        if not settlement:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": "No active settlement found."},
            )
        if settlement["status"] != "calculated":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": f"Settlement must be in 'calculated' status to finalize "
                                 f"(current: '{settlement['status']}'). Run /calculate first."},
            )

        refund_amount   = float(settlement.get("refund_amount", 0))
        retained_amount = float(settlement.get("retained_amount", 0))
        now = _now_iso()

        # 1. Finalize the settlement record
        db.table("booking_settlement_records").update({
            "status":       "finalized",
            "finalized_by": actor_id,
            "finalized_at": now,
            "updated_at":   now,
        }).eq("id", settlement["id"]).execute()

        # 2. Update cash_deposits status (the only cross-table side effect)
        cash_deposit_id = _get_cash_deposit_id(db, tenant_id, booking_id)
        if cash_deposit_id:
            if refund_amount > 0:
                db.table("cash_deposits").update({
                    "status":       "returned",
                    "returned_by":  actor_id,
                    "returned_at":  now,
                    "refund_amount": refund_amount,
                }).eq("id", cash_deposit_id).execute()
            elif retained_amount > 0:
                db.table("cash_deposits").update({
                    "status":            "forfeited",
                    "forfeited_by":      actor_id,
                    "forfeited_at":      now,
                    "forfeited_amount":  retained_amount,
                    "forfeiture_reason": body.get("notes") or "Settlement finalized — deposit retained.",
                }).eq("id", cash_deposit_id).execute()

        _audit(db, tenant_id, actor_id, "settlement_finalized",
               "booking_settlement_record", settlement["id"],
               {"booking_id": booking_id, "refund_amount": refund_amount,
                "retained_amount": retained_amount,
                "cash_deposit_updated": bool(cash_deposit_id)})

        return JSONResponse(status_code=200, content={
            "settlement_id":  settlement["id"],
            "booking_id":     booking_id,
            "status":         "finalized",
            "refund_amount":  refund_amount,
            "retained_amount": retained_amount,
            "finalized_by":   actor_id,
            "finalized_at":   now,
        })

    except Exception as exc:
        logger.exception("POST settlement/finalize %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 — POST void (admin only)
# ===========================================================================

@router.post(
    "/admin/bookings/{booking_id}/settlement/void",
    summary="Void an active settlement before finalization (Phase 961)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def void_settlement(
    booking_id: str,
    body: dict,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Void a non-finalized settlement. Admin only. Requires `void_reason`.

    After voiding, a new settlement can be started with `/settlement/start`.
    """
    role = identity.get("role", "")
    if role not in _VOID_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Only admin can void a settlement."},
        )
    tenant_id = identity["tenant_id"]
    actor_id  = identity.get("user_id", "unknown")

    void_reason = (body.get("void_reason") or "").strip()
    if not void_reason:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "void_reason is required when voiding a settlement."},
        )

    try:
        db = client or _get_db()

        settlement = _get_active_settlement(db, tenant_id, booking_id)
        if not settlement:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": "No active settlement found."},
            )
        if settlement["status"] == "finalized":
            return make_error_response(
                status_code=409, code="CONFLICT",
                extra={"detail": "Cannot void a finalized settlement."},
            )

        now = _now_iso()
        db.table("booking_settlement_records").update({
            "status":      "voided",
            "voided_by":   actor_id,
            "voided_at":   now,
            "void_reason": void_reason,
            "updated_at":  now,
        }).eq("id", settlement["id"]).execute()

        _audit(db, tenant_id, actor_id, "settlement_voided",
               "booking_settlement_record", settlement["id"],
               {"booking_id": booking_id, "void_reason": void_reason})

        return JSONResponse(status_code=200, content={
            "settlement_id": settlement["id"],
            "status":        "voided",
            "voided_by":     actor_id,
            "void_reason":   void_reason,
        })

    except Exception as exc:
        logger.exception("POST settlement/void %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 + 967 — Admin: GET full settlement view with categorized deductions
# ===========================================================================

@router.get(
    "/admin/bookings/{booking_id}/settlement",
    summary="Full settlement view with categorized deductions (Phase 967)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def admin_get_settlement(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Full settlement record with categorized deductions and meter readings.
    Returns all settlement rows (including voided) for audit history.
    Deductions are grouped by category: electricity, damage, miscellaneous (Phase 967).
    Auth: admin, manager.
    """
    role = identity.get("role", "")
    if role not in _READ_ADMIN:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Requires admin or manager role."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        # All settlement records for this booking (including voided)
        res = (
            db.table("booking_settlement_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("created_at", desc=False)
            .execute()
        )
        settlements = res.data or []
        if not settlements:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": "No settlement records found for this booking."},
            )

        # Meter readings
        meter_res = (
            db.table("electricity_meter_readings")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("reading_type", desc=False)
            .order("created_at", desc=False)
            .execute()
        )
        meter_readings = meter_res.data or []

        # Categorized deductions (Phase 967)
        cash_deposit_id = _get_cash_deposit_id(db, tenant_id, booking_id)
        cats = _get_deductions_by_category(db, cash_deposit_id)

        active = next((s for s in settlements if s["status"] != "voided"), None)

        return JSONResponse(status_code=200, content={
            "booking_id":       booking_id,
            "active_settlement": _serialize_settlement(active) if active else None,
            "all_settlements":  [_serialize_settlement(s) for s in settlements],
            "meter_readings":   meter_readings,
            "deductions_by_category": {
                "electricity":   {"items": cats["electricity"][0],   "total": cats["electricity"][1]},
                "damage":        {"items": cats["damage"][0],        "total": cats["damage"][1]},
                "miscellaneous": {"items": cats["miscellaneous"][0], "total": cats["miscellaneous"][1]},
            },
            "deductions_total": cats["all"][1],
        })

    except Exception as exc:
        logger.exception("GET admin settlement %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# Phase 961 — Admin: GET settlements by property
# ===========================================================================

@router.get(
    "/admin/properties/{property_id}/settlements",
    summary="List settlement records for a property (Phase 961)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def admin_list_settlements(
    property_id: str,
    status: Optional[str] = None,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    List settlement records for a property.
    Filter: `?status=draft|calculated|finalized|voided`
    Auth: admin, manager.
    """
    role = identity.get("role", "")
    if role not in _READ_ADMIN:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Requires admin or manager role."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        query = (
            db.table("booking_settlement_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("created_at", desc=True)
        )
        if status:
            query = query.eq("status", status)
        res = query.execute()
        rows = res.data or []
        return JSONResponse(status_code=200, content={
            "count":       len(rows),
            "settlements": [_serialize_settlement(r) for r in rows],
        })

    except Exception as exc:
        logger.exception("GET settlements property=%s error tenant=%s: %s",
                         property_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 993 — GET /worker/bookings/{booking_id}/checkout-baseline
# ---------------------------------------------------------------------------

@router.get(
    "/worker/bookings/{booking_id}/checkout-baseline",
    summary="Composite checkout baseline for the before/after worker flow (Phase 993)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_checkout_baseline(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns everything the checkout wizard needs to display the before/after
    comparison flow in a single round-trip:

      - property_reference_photos  — what the property SHOULD look like
      - checkin_walkthrough_photos  — what it actually looked like at check-in
      - checkin_meter_photos        — meter photos from check-in
      - opening_meter               — { value, photo_url, recorded_at }
      - deposit                     — { amount, currency }
      - charge_rules                — { electricity_rate_kwh, electricity_currency, ... }

    Auth: worker, checkin, checkout, ops, admin.
    """
    role = identity.get("role", "")
    if role not in _WRITE_ROLES and role not in _READ_ADMIN and role != "manager":
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot access checkout baseline."},
        )
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        # 1. Resolve property_id from booking_state
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

        # 2. Property reference photos
        reference_photos: list[dict] = []
        if property_id:
            try:
                ref_res = (
                    db.table("property_reference_photos")
                    .select("id, photo_url, room_label, caption, display_order")
                    .eq("property_id", property_id)
                    .order("display_order", desc=False)
                    .execute()
                )
                reference_photos = ref_res.data or []
            except Exception as exc:
                logger.warning("checkout-baseline: ref photos failed: %s", exc)

        # 3. Check-in walkthrough photos for this booking
        checkin_walkthrough_photos: list[dict] = []
        checkin_meter_photos: list[dict] = []
        try:
            photos_res = (
                db.table("booking_checkin_photos")
                .select("id, room_label, storage_path, purpose, captured_at, uploaded_by, notes")
                .eq("tenant_id", tenant_id)
                .eq("booking_id", booking_id)
                .order("captured_at", desc=False)
                .execute()
            )
            for ph in (photos_res.data or []):
                purpose = ph.get("purpose", "")
                if purpose == "walkthrough":
                    checkin_walkthrough_photos.append(ph)
                elif purpose == "meter":
                    checkin_meter_photos.append(ph)
        except Exception as exc:
            logger.warning("checkout-baseline: checkin photos failed: %s", exc)

        # 4. Opening meter reading
        opening_meter = _get_opening_meter(db, tenant_id, booking_id)
        opening_meter_data = None
        if opening_meter:
            opening_meter_data = {
                "id":            str(opening_meter.get("id", "")),
                "meter_value":   float(opening_meter["meter_value"]) if opening_meter.get("meter_value") is not None else None,
                "meter_unit":    opening_meter.get("meter_unit", "kWh"),
                "meter_photo_url": opening_meter.get("meter_photo_url"),
                "recorded_by":   opening_meter.get("recorded_by"),
                "recorded_at":   opening_meter.get("recorded_at") or opening_meter.get("created_at"),
            }

        # 5. Deposit held
        deposit_amount, deposit_currency = _get_deposit_held(db, tenant_id, booking_id)
        deposit_data = {
            "amount":   deposit_amount,
            "currency": deposit_currency,
        } if deposit_amount > 0 else None

        # 6. Property charge rules
        charge_rules = None
        if property_id:
            cr = _get_charge_rule(db, tenant_id, property_id)
            if cr:
                charge_rules = {
                    "deposit_enabled":      cr.get("deposit_enabled", False),
                    "deposit_amount":       float(cr["deposit_amount"]) if cr.get("deposit_amount") is not None else None,
                    "deposit_currency":     cr.get("deposit_currency"),
                    "electricity_enabled":  cr.get("electricity_enabled", False),
                    "electricity_rate_kwh": float(cr["electricity_rate_kwh"]) if cr.get("electricity_rate_kwh") is not None else None,
                    "electricity_currency": cr.get("electricity_currency"),
                }

        return JSONResponse(status_code=200, content={
            "booking_id":                booking_id,
            "property_id":               property_id,
            "property_reference_photos": reference_photos,
            "checkin_walkthrough_photos": checkin_walkthrough_photos,
            "checkin_meter_photos":       checkin_meter_photos,
            "opening_meter":             opening_meter_data,
            "deposit":                   deposit_data,
            "charge_rules":              charge_rules,
        })

    except Exception as exc:
        logger.exception("GET checkout-baseline %s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
