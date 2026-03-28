"""
Phase 962 — Admin Settlement History Surface
=============================================

Pure read-only aggregation layer for admin. No new DB tables.
Assembles durable, long-term settlement history from the 8 existing tables
written by Phases 687–961, corrected by Phases 963–967.

Use case: admin reviews a booking's complete settlement story months later —
who collected the deposit, what the meter readings were (with photos), what
was deducted (electricity + damage + miscellaneous), final refund/retain
split, and the full audit trail of every actor who touched it.

Endpoints (all read-only, all admin/manager only):

    GET /admin/settlements
        Cross-property settlement history list with booking context.
        Filters: ?property_id=  ?status=  ?date_from=  ?date_to=
                 ?limit=  ?offset=

    GET /admin/settlements/summary
        Portfolio aggregate: counts + amount totals for a time window.
        Filters: same as list.
        NOTE: registered BEFORE /{settlement_id} to prevent routing collision.

    GET /admin/settlements/{settlement_id}/full-record
        Complete durable record — all 8 source tables joined for one settlement.

    GET /admin/bookings/{booking_id}/settlement-record
        Full record keyed by booking_id (resolver finds the settlement).

Role access:
    admin, manager — full access to all endpoints.
    ops, owner, worker — no access (403).

Invariants:
    - Strictly read-only. No writes, no side effects.
    - Tenant isolation enforced on every query (tenant_id always from JWT).
    - admin_audit_log trail is included in full records, filtered to
      settlement-related entity types per booking.
    - Summary returns 0s when no records match (never 404 on empty).
    - Long-term durability is guaranteed by the source tables (no TTL, no archival).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_identity_simple as jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["settlement-history"])

_ALLOWED_ROLES = frozenset({"admin", "manager"})


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Role guard
# ---------------------------------------------------------------------------

def _assert_role(identity: dict) -> Optional[JSONResponse]:
    role = identity.get("role", "")
    if role not in _ALLOWED_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": "Settlement history requires admin or manager role."},
        )
    return None


# ---------------------------------------------------------------------------
# Record assembly helpers
# ---------------------------------------------------------------------------

def _get_booking_context(db: Any, tenant_id: str, booking_id: str) -> dict:
    """Pull guest name, dates, property_id from booking_state."""
    try:
        res = (
            db.table("booking_state")
            .select("booking_id, guest_name, check_in, check_out, property_id, status")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else {}
    except Exception:
        return {}


def _get_checkin_deposit(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("checkin_deposit_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_cash_deposit(db: Any, tenant_id: str, booking_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("cash_deposits")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_deductions_categorized(db: Any, deposit_id: Optional[str]) -> dict:
    """
    Get all deductions grouped by category (Phase 967).
    Returns {
        'all': [all rows],
        'by_category': {
            'electricity':   {'items': [...], 'total': float},
            'damage':        {'items': [...], 'total': float},
            'miscellaneous': {'items': [...], 'total': float},
        },
        'grand_total': float,
    }
    """
    empty = {
        "all": [],
        "by_category": {
            "electricity":   {"items": [], "total": 0.0},
            "damage":        {"items": [], "total": 0.0},
            "miscellaneous": {"items": [], "total": 0.0},
        },
        "grand_total": 0.0,
    }
    if not deposit_id:
        return empty
    try:
        res = (
            db.table("deposit_deductions")
            .select("*")
            .eq("deposit_id", deposit_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return empty

        by_cat: dict[str, list[dict]] = {"electricity": [], "damage": [], "miscellaneous": []}
        for r in rows:
            cat = r.get("category", "damage")
            if cat in by_cat:
                by_cat[cat].append(r)
            else:
                by_cat["miscellaneous"].append(r)

        return {
            "all": rows,
            "by_category": {
                cat: {
                    "items": items,
                    "total": round(sum(float(r.get("amount", 0)) for r in items), 2),
                }
                for cat, items in by_cat.items()
            },
            "grand_total": round(sum(float(r.get("amount", 0)) for r in rows), 2),
        }
    except Exception:
        return empty


def _get_meter_readings(db: Any, tenant_id: str, booking_id: str) -> dict:
    """
    Returns { opening: dict|None, closing: dict|None }
    Picks the latest reading of each type.
    """
    result: dict = {"opening": None, "closing": None}
    for rtype in ("opening", "closing"):
        try:
            res = (
                db.table("electricity_meter_readings")
                .select("id, reading_type, meter_value, meter_unit, "
                        "meter_photo_url, recorded_by, recorded_at, "
                        "supercedes_id, notes, created_at")
                .eq("tenant_id", tenant_id)
                .eq("booking_id", booking_id)
                .eq("reading_type", rtype)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = res.data or []
            result[rtype] = rows[0] if rows else None
        except Exception:
            pass
    return result


def _get_charge_rule(db: Any, tenant_id: str, property_id: str) -> Optional[dict]:
    try:
        res = (
            db.table("property_charge_rules")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def _get_audit_trail(db: Any, tenant_id: str, booking_id: str) -> list[dict]:
    """
    Pulls admin_audit_log events related to the settlement lifecycle for this booking.
    Filters by entity_type = settlement-related types and details.booking_id match.
    """
    settlement_types = (
        "booking_settlement_record",
        "electricity_meter_reading",
        "checkin_deposit_record",
        "deposit_suggestion",
    )
    events: list[dict] = []
    for etype in settlement_types:
        try:
            res = (
                db.table("admin_audit_log")
                .select("action, actor_id, entity_type, entity_id, details, performed_at")
                .eq("tenant_id", tenant_id)
                .eq("entity_type", etype)
                .order("performed_at", desc=False)
                .limit(200)
                .execute()
            )
            for row in (res.data or []):
                # Keep only rows that are linked to this booking
                details = row.get("details") or {}
                if isinstance(details, dict) and details.get("booking_id") == booking_id:
                    events.append(row)
        except Exception:
            pass
    events.sort(key=lambda r: r.get("performed_at", ""))
    return events


def _assemble_full_record(db: Any, tenant_id: str, settlement: dict) -> dict:
    """
    Join all 8 source tables into the durable full record for one settlement.
    Phase 967: deductions are grouped by category (electricity, damage, miscellaneous).
    """
    booking_id  = settlement["booking_id"]
    property_id = settlement["property_id"]

    booking_ctx   = _get_booking_context(db, tenant_id, booking_id)
    checkin_dep   = _get_checkin_deposit(db, tenant_id, booking_id)
    cash_dep      = _get_cash_deposit(db, tenant_id, booking_id)
    deposit_id    = cash_dep["id"] if cash_dep else None
    deductions    = _get_deductions_categorized(db, deposit_id)
    meters        = _get_meter_readings(db, tenant_id, booking_id)
    charge_rule   = _get_charge_rule(db, tenant_id, property_id)
    audit_trail   = _get_audit_trail(db, tenant_id, booking_id)

    # Electricity summary (from settlement snapshot if finalized, else computed live)
    elec = {
        "opening":    meters["opening"],
        "closing":    meters["closing"],
        "kwh_used":   settlement.get("electricity_kwh_used"),
        "rate_kwh":   settlement.get("electricity_rate_kwh"),
        "charged":    settlement.get("electricity_charged"),
        "currency":   settlement.get("electricity_currency"),
    }

    return {
        "settlement":        settlement,
        "booking": {
            "booking_id":    booking_id,
            "guest_name":    booking_ctx.get("guest_name"),
            "check_in":      booking_ctx.get("check_in"),
            "check_out":     booking_ctx.get("check_out"),
            "property_id":   property_id,
            "status":        booking_ctx.get("status"),
        },
        "deposit": {
            "checkin_record":    checkin_dep,
            "cash_deposit":      cash_dep,
            "deductions":        deductions["by_category"],
            "total_deductions":  deductions["grand_total"],
        },
        "electricity":          elec,
        "charge_rule_at_stay":  charge_rule,
        "audit_trail":          audit_trail,
    }


# ===========================================================================
# GET /admin/settlements  — cross-property history list
# ===========================================================================

@router.get(
    "/admin/settlements",
    summary="Cross-property settlement history list (Phase 962)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_settlements_history(
    property_id: Optional[str]  = Query(None),
    status:      Optional[str]  = Query(None),
    date_from:   Optional[str]  = Query(None, description="ISO date YYYY-MM-DD"),
    date_to:     Optional[str]  = Query(None, description="ISO date YYYY-MM-DD"),
    limit:       int            = Query(50, ge=1, le=200),
    offset:      int            = Query(0, ge=0),
    identity:    dict           = Depends(jwt_identity),
    client:      Optional[Any]  = None,
) -> JSONResponse:
    """
    Cross-property settlement history for the tenant.

    Returns `booking_settlement_records` rows enriched with booking context
    (guest name, check-in/out dates). Ordered by created_at descending
    (most recent first).

    **Filters:**
    - `?property_id=` — filter to a single property
    - `?status=draft|calculated|finalized|voided`
    - `?date_from=YYYY-MM-DD` — created_at ≥ this date
    - `?date_to=YYYY-MM-DD` — created_at ≤ this date
    - `?limit=` (1–200, default 50)
    - `?offset=` (pagination)

    Auth: admin, manager.
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        query = (
            db.table("booking_settlement_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(limit)
            .offset(offset)
        )
        if property_id:
            query = query.eq("property_id", property_id)
        if status:
            query = query.eq("status", status)
        if date_from:
            query = query.gte("created_at", f"{date_from}T00:00:00Z")
        if date_to:
            query = query.lte("created_at", f"{date_to}T23:59:59Z")

        res = query.execute()
        rows = res.data or []

        # Enrich each row with booking context (lean — no full record assembly)
        enriched: list[dict] = []
        for row in rows:
            bid = row["booking_id"]
            ctx = _get_booking_context(db, tenant_id, bid)
            enriched.append({
                "settlement_id":   row["id"],
                "booking_id":      bid,
                "property_id":     row["property_id"],
                "status":          row["status"],
                "deposit_held":    row.get("deposit_held"),
                "deposit_currency": row.get("deposit_currency"),
                "electricity_kwh_used":  row.get("electricity_kwh_used"),
                "electricity_charged":   row.get("electricity_charged"),
                "damage_deductions_total": row.get("damage_deductions_total"),
                "miscellaneous_deductions_total": row.get("miscellaneous_deductions_total"),
                "total_deductions":      row.get("total_deductions"),
                "refund_amount":         row.get("refund_amount"),
                "retained_amount":       row.get("retained_amount"),
                "finalized_by":          row.get("finalized_by"),
                "finalized_at":          row.get("finalized_at"),
                "created_at":            row.get("created_at"),
                # Booking context
                "guest_name":    ctx.get("guest_name"),
                "check_in":      ctx.get("check_in"),
                "check_out":     ctx.get("check_out"),
            })

        return JSONResponse(status_code=200, content={
            "count":   len(enriched),
            "offset":  offset,
            "limit":   limit,
            "records": enriched,
        })

    except Exception as exc:
        logger.exception("GET /admin/settlements error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# GET /admin/settlements/summary  — portfolio aggregate
# NOTE: must be registered BEFORE /{settlement_id} route
# ===========================================================================

@router.get(
    "/admin/settlements/summary",
    summary="Portfolio settlement aggregate for a time window (Phase 962)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def settlements_summary(
    property_id: Optional[str] = Query(None),
    date_from:   Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    date_to:     Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
    identity:    dict          = Depends(jwt_identity),
    client:      Optional[Any] = None,
) -> JSONResponse:
    """
    Portfolio aggregate for a time window.

    Returns counts and total amounts grouped across all matching settlements.

    **Response fields:**
    - `total_count` — all settlements in the period
    - `by_status` — `{ draft, calculated, finalized, voided }` counts
    - `totals` — `{ deposit_held, refunded, retained, electricity_charged, damage_deductions }`
      across all **finalized** settlements only (open ones are excluded from financial totals)

    Auth: admin, manager.
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        query = (
            db.table("booking_settlement_records")
            .select(
                "status, deposit_held, refund_amount, retained_amount, "
                "electricity_charged, damage_deductions_total, "
                "miscellaneous_deductions_total"
            )
            .eq("tenant_id", tenant_id)
        )
        if property_id:
            query = query.eq("property_id", property_id)
        if date_from:
            query = query.gte("created_at", f"{date_from}T00:00:00Z")
        if date_to:
            query = query.lte("created_at", f"{date_to}T23:59:59Z")

        res = query.execute()
        rows = res.data or []

        by_status: dict[str, int] = {"draft": 0, "calculated": 0, "finalized": 0, "voided": 0}
        totals = {
            "deposit_held":              0.0,
            "refunded":                  0.0,
            "retained":                  0.0,
            "electricity_charged":       0.0,
            "damage_deductions":         0.0,
            "miscellaneous_deductions":  0.0,
        }

        for row in rows:
            s = row.get("status", "draft")
            by_status[s] = by_status.get(s, 0) + 1
            if s == "finalized":
                totals["deposit_held"]             += float(row.get("deposit_held") or 0)
                totals["refunded"]                 += float(row.get("refund_amount") or 0)
                totals["retained"]                 += float(row.get("retained_amount") or 0)
                totals["electricity_charged"]      += float(row.get("electricity_charged") or 0)
                totals["damage_deductions"]        += float(row.get("damage_deductions_total") or 0)
                totals["miscellaneous_deductions"] += float(row.get("miscellaneous_deductions_total") or 0)

        # Round totals
        totals = {k: round(v, 2) for k, v in totals.items()}

        return JSONResponse(status_code=200, content={
            "filters": {
                "property_id": property_id,
                "date_from":   date_from,
                "date_to":     date_to,
            },
            "total_count":      len(rows),
            "by_status":        by_status,
            "finalized_totals": totals,
        })

    except Exception as exc:
        logger.exception("GET /admin/settlements/summary error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# GET /admin/settlements/{settlement_id}/full-record
# ===========================================================================

@router.get(
    "/admin/settlements/{settlement_id}/full-record",
    summary="Complete durable settlement record by settlement_id (Phase 962)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_full_record_by_settlement(
    settlement_id: str,
    identity:      dict          = Depends(jwt_identity),
    client:        Optional[Any] = None,
) -> JSONResponse:
    """
    Complete durable record for one settlement, joining all 8 source tables.

    Returns the full story of what happened for a booking:
    deposit collected (checkin_deposit_records + cash_deposits),
    meter readings with photos (electricity_meter_readings),
    damage deductions (deposit_deductions),
    final amounts (booking_settlement_records),
    charge rule in effect at the time (property_charge_rules),
    and the full audit trail (admin_audit_log).

    Auth: admin, manager.
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()
        res = (
            db.table("booking_settlement_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("id", settlement_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Settlement '{settlement_id}' not found."},
            )
        record = _assemble_full_record(db, tenant_id, rows[0])
        return JSONResponse(status_code=200, content=record)

    except Exception as exc:
        logger.exception("GET /admin/settlements/%s/full-record error tenant=%s: %s",
                         settlement_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ===========================================================================
# GET /admin/bookings/{booking_id}/settlement-record
# ===========================================================================

@router.get(
    "/admin/bookings/{booking_id}/settlement-record",
    summary="Complete durable settlement record by booking_id (Phase 962)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_full_record_by_booking(
    booking_id: str,
    identity:   dict          = Depends(jwt_identity),
    client:     Optional[Any] = None,
) -> JSONResponse:
    """
    Complete durable settlement record keyed by booking_id.

    Returns the most recent non-voided settlement for this booking.
    If only voided settlements exist, returns the latest voided with a
    `voided_only: true` flag.

    Same response shape as `/{settlement_id}/full-record`.

    Auth: admin, manager.
    """
    err = _assert_role(identity)
    if err:
        return err
    tenant_id = identity["tenant_id"]

    try:
        db = client or _get_db()

        # Prefer active (non-voided) settlement
        res = (
            db.table("booking_settlement_records")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("created_at", desc=True)
            .execute()
        )
        all_rows = res.data or []
        if not all_rows:
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"No settlement record found for booking '{booking_id}'."},
            )

        active = next((r for r in all_rows if r["status"] != "voided"), None)
        settlement = active if active else all_rows[0]
        voided_only = active is None

        record = _assemble_full_record(db, tenant_id, settlement)
        record["voided_only"] = voided_only

        # Also include all settlement history for this booking
        record["all_settlements"] = [
            {
                "id":           r["id"],
                "status":       r["status"],
                "created_at":   r.get("created_at"),
                "finalized_at": r.get("finalized_at"),
                "voided_at":    r.get("voided_at"),
                "void_reason":  r.get("void_reason"),
            }
            for r in all_rows
        ]

        return JSONResponse(status_code=200, content=record)

    except Exception as exc:
        logger.exception("GET /admin/bookings/%s/settlement-record error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
