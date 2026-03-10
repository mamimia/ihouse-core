"""
Phase 215 — Automated Revenue Reports

Per-property revenue summary API. Builds on the owner-statement and cashflow
infrastructure (booking_financial_facts, owner_statement_router helpers).

Endpoints:
    GET /revenue-report/{property_id}
        Single-property revenue summary for a date range.
        Groups by calendar month within the range.
        Returns monthly breakdown + overall totals.
        Supports optional management_fee_pct deduction.

    GET /revenue-report/portfolio
        Cross-property revenue summary for a date range.
        Returns one summary row per property found in booking_financial_facts.
        Tenant-scoped. Sorted by gross_total DESC.

Design:
    - Reads `booking_financial_facts` ONLY. Never reads booking_state.
    - Deduplication: most-recent recorded_at per booking_id (same rule as
      owner_statement_router).
    - Multi-currency properties: monetary totals are None, currency = "MIXED".
    - Management fee applies to net_to_property (same formula as owner statement).
    - Date range: `from_month` (YYYY-MM) and `to_month` (YYYY-MM) query params.
      Both required. to_month must be >= from_month. Max range: 24 months.
    - OTA_COLLECTING excluded from owner_net (same rule as owner statement).

Invariants:
    - JWT auth required.
    - Tenant isolation.
    - Never reads or writes booking_state.
    - All monetary values are strings with 2 decimal places.
    - Epistemic tier: A/B/C — worst tier wins per period and in totals.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone, date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from api.financial_aggregation_router import (
    _dedup_latest,
    _fmt,
    _to_decimal,
)
from api.financial_dashboard_router import (
    _tier,
    _worst_tier,
    _project_lifecycle_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["revenue-report"])

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_MAX_RANGE_MONTHS = 24


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------

def _month_start_end(month: str) -> Tuple[str, str]:
    """Return ISO start/end timestamps for a YYYY-MM month for DB range queries."""
    year, mon = int(month[:4]), int(month[5:7])
    start = f"{year:04d}-{mon:02d}-01T00:00:00"
    # next month start
    if mon == 12:
        end = f"{year + 1:04d}-01-01T00:00:00"
    else:
        end = f"{year:04d}-{mon + 1:02d}-01T00:00:00"
    return start, end


def _months_between(from_month: str, to_month: str) -> List[str]:
    """Return list of YYYY-MM strings from from_month to to_month inclusive."""
    months = []
    year, mon = int(from_month[:4]), int(from_month[5:7])
    end_year, end_mon = int(to_month[:4]), int(to_month[5:7])
    while (year, mon) <= (end_year, end_mon):
        months.append(f"{year:04d}-{mon:02d}")
        mon += 1
        if mon > 12:
            mon = 1
            year += 1
    return months


def _month_diff(from_month: str, to_month: str) -> int:
    """Return number of months between two YYYY-MM strings (inclusive)."""
    y1, m1 = int(from_month[:4]), int(from_month[5:7])
    y2, m2 = int(to_month[:4]), int(to_month[5:7])
    return (y2 - y1) * 12 + (m2 - m1) + 1


def _parse_mgmt_fee(raw: Optional[str]) -> Optional[Decimal]:
    if raw is None:
        return Decimal("0")
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if val < Decimal("0") or val > Decimal("100"):
        return None
    return val


def _optional_str(val: Optional[Decimal]) -> Optional[str]:
    return _fmt(val) if val is not None else None


def _build_month_summary(
    rows: List[dict],
    month: str,
    mgmt_fee_pct: Decimal,
) -> Dict[str, Any]:
    """Aggregate deduplicated rows for a single month into a summary dict."""
    deduped = _dedup_latest(rows)
    if not deduped:
        return {
            "month": month,
            "booking_count": 0,
            "currency": None,
            "gross_total": None,
            "ota_commission_total": None,
            "net_to_property_total": None,
            "management_fee_amount": None,
            "owner_net_total": None,
            "ota_collecting_excluded": 0,
            "epistemic_tier": "C",
        }

    currencies = {r.get("currency") for r in deduped if r.get("currency")}
    is_mixed = len(currencies) > 1
    currency = "MIXED" if is_mixed else (next(iter(currencies), None))

    gross_vals: List[Decimal] = []
    comm_vals: List[Decimal] = []
    net_vals: List[Decimal] = []
    tiers: list = []
    ota_collecting = 0

    for row in deduped:
        event_kind = row.get("event_kind") or "BOOKING_CREATED"
        confidence = row.get("source_confidence") or "PARTIAL"
        lifecycle = _project_lifecycle_status(row, event_kind)
        tiers.append(_tier(confidence))

        if lifecycle == "OTA_COLLECTING":
            ota_collecting += 1

        if not is_mixed:
            g = _to_decimal(row.get("total_price"))
            c = _to_decimal(row.get("ota_commission"))
            n = _to_decimal(row.get("net_to_property"))
            if g and g > Decimal("0"):
                gross_vals.append(g)
            if c and c > Decimal("0"):
                comm_vals.append(c)
            if n and n > Decimal("0") and lifecycle != "OTA_COLLECTING":
                net_vals.append(n)

    if is_mixed:
        gross_total = None
        comm_total = None
        net_total = None
        mgmt_amount = None
        owner_net = None
    else:
        gross_total = sum(gross_vals, Decimal("0")) if gross_vals else None
        comm_total  = sum(comm_vals, Decimal("0")) if comm_vals else None
        net_total   = sum(net_vals, Decimal("0")) if net_vals else None

        if net_total is not None and mgmt_fee_pct > Decimal("0"):
            mgmt_amount = (net_total * mgmt_fee_pct / Decimal("100")).quantize(Decimal("0.01"))
            owner_net   = (net_total - mgmt_amount).quantize(Decimal("0.01"))
        else:
            mgmt_amount = None
            owner_net = net_total

    worst = _worst_tier(tiers) if tiers else "C"
    return {
        "month": month,
        "booking_count": len(deduped),
        "currency": currency,
        "gross_total": _optional_str(gross_total),
        "ota_commission_total": _optional_str(comm_total),
        "net_to_property_total": _optional_str(net_total),
        "management_fee_amount": _optional_str(mgmt_amount),
        "owner_net_total": _optional_str(owner_net),
        "ota_collecting_excluded": ota_collecting,
        "epistemic_tier": worst,
    }


def _aggregate_months(monthly: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Roll up a list of monthly summaries into an overall total."""
    total_bookings = sum(m["booking_count"] for m in monthly)
    currencies = {m["currency"] for m in monthly if m["currency"] and m["currency"] != "MIXED"}
    is_mixed = len(currencies) > 1 or any(m.get("currency") == "MIXED" for m in monthly)
    currency = "MIXED" if is_mixed else (next(iter(currencies), None))

    tiers = [m["epistemic_tier"] for m in monthly if m["epistemic_tier"]]
    worst = _worst_tier(tiers) if tiers else "C"

    def _sum_field(field: str) -> Optional[str]:
        if is_mixed:
            return None
        vals = [Decimal(m[field]) for m in monthly if m.get(field) is not None]
        return _fmt(sum(vals, Decimal("0"))) if vals else None

    return {
        "total_booking_count": total_bookings,
        "currency": currency,
        "gross_total": _sum_field("gross_total"),
        "ota_commission_total": _sum_field("ota_commission_total"),
        "net_to_property_total": _sum_field("net_to_property_total"),
        "management_fee_total": _sum_field("management_fee_amount"),
        "owner_net_total": _sum_field("owner_net_total"),
        "ota_collecting_excluded_total": sum(m["ota_collecting_excluded"] for m in monthly),
        "overall_epistemic_tier": worst,
    }


# ---------------------------------------------------------------------------
# GET /revenue-report/portfolio — cross-property summary
# NOTE: Must be registered BEFORE /{property_id} to avoid FastAPI capturing
# the literal path segment 'portfolio' as a path parameter.
# ---------------------------------------------------------------------------

@router.get(
    "/revenue-report/portfolio",
    tags=["revenue-report"],
    summary="Automated revenue report — portfolio view (all properties) (Phase 215)",
    description=(
        "Cross-property revenue summary for a date range.\\n\\n"
        "Returns one summary row per property found in `booking_financial_facts`, "
        "sorted by `gross_total` descending (best-performing properties first).\\n\\n"
        "**Required:** `from_month`, `to_month` (YYYY-MM).\\n"
        "**Optional:** `management_fee_pct`.\\n\\n"
        "**Source:** `booking_financial_facts` only. Tenant-scoped."
    ),
    responses={
        200: {"description": "Portfolio revenue summary — one row per property."},
        400: {"description": "Invalid date range or management_fee_pct."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_portfolio_revenue_report(
    from_month: Optional[str] = Query(default=None, description="Start month YYYY-MM"),
    to_month: Optional[str]   = Query(default=None, description="End month YYYY-MM"),
    management_fee_pct: Optional[str] = Query(default=None, description="Management fee % (0–100)"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if not from_month or not _MONTH_RE.match(from_month):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'from_month' is required and must be YYYY-MM format."},
        )
    if not to_month or not _MONTH_RE.match(to_month):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'to_month' is required and must be YYYY-MM format."},
        )
    if to_month < from_month:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'to_month' must be >= 'from_month'."},
        )
    if _month_diff(from_month, to_month) > _MAX_RANGE_MONTHS:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Date range must not exceed {_MAX_RANGE_MONTHS} months."},
        )

    mgmt_fee = _parse_mgmt_fee(management_fee_pct)
    if mgmt_fee is None:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'management_fee_pct' must be between 0.0 and 100.0."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        range_start, _ = _month_start_end(from_month)
        _, range_end   = _month_start_end(to_month)

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("recorded_at", range_start)
            .lt("recorded_at", range_end)
            .order("recorded_at", desc=False)
            .execute()
        )
        all_rows: List[dict] = result.data or []

        # Group by property_id
        by_property: Dict[str, List[dict]] = {}
        for row in all_rows:
            pid = row.get("property_id") or "unknown"
            by_property.setdefault(pid, []).append(row)

        property_summaries: List[Dict[str, Any]] = []
        for pid, rows in by_property.items():
            months = _months_between(from_month, to_month)
            monthly_list: List[Dict[str, Any]] = []
            for month in months:
                m_start, m_end = _month_start_end(month)
                month_rows = [
                    r for r in rows
                    if r.get("recorded_at", "") >= m_start and r.get("recorded_at", "") < m_end
                ]
                monthly_list.append(_build_month_summary(month_rows, month, mgmt_fee))

            totals = _aggregate_months(monthly_list)
            totals["property_id"] = pid
            property_summaries.append(totals)

        # Sort by gross_total DESC (None last)
        def _sort_key(p: dict):
            gt = p.get("gross_total")
            return -Decimal(gt) if gt else Decimal("-999999999")

        property_summaries.sort(key=_sort_key)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":  tenant_id,
                "from_month": from_month,
                "to_month":   to_month,
                "management_fee_pct": _fmt(mgmt_fee),
                "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "property_count": len(property_summaries),
                "properties": property_summaries,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /revenue-report/portfolio error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /revenue-report/{property_id} — single-property monthly breakdown
# NOTE: Must be registered AFTER /portfolio — otherwise FastAPI captures the
# literal segment 'portfolio' as property_id.
# ---------------------------------------------------------------------------

@router.get(
    "/revenue-report/{property_id}",
    tags=["revenue-report"],
    summary="Automated revenue report — single property, monthly breakdown (Phase 215)",
    description=(
        "Per-property revenue summary grouped by calendar month over a date range.\\n\\n"
        "Returns `monthly` breakdown + `totals` (rolled up across all months).\\n\\n"
        "**Required query params:** `from_month` (YYYY-MM), `to_month` (YYYY-MM).\\n"
        "Max range: 24 months.\\n\\n"
        "**Optional:** `management_fee_pct` (0.0–100.0) — deducted from net_to_property.\\n\\n"
        "**Source:** `booking_financial_facts` only. Never reads `booking_state`.\\n\\n"
        "OTA_COLLECTING bookings are excluded from `owner_net_total` (same rule as owner statement)."
    ),
    responses={
        200: {"description": "Revenue report with monthly breakdown and totals."},
        400: {"description": "Invalid date range or management_fee_pct."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "No records found for this property in the requested range."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_revenue_report(
    property_id: str,
    from_month: Optional[str] = Query(default=None, description="Start month YYYY-MM (inclusive)"),
    to_month: Optional[str]   = Query(default=None, description="End month YYYY-MM (inclusive)"),
    management_fee_pct: Optional[str] = Query(default=None, description="Management fee % (0–100)"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    # Validate month params
    if not from_month or not _MONTH_RE.match(from_month):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'from_month' is required and must be YYYY-MM format."},
        )
    if not to_month or not _MONTH_RE.match(to_month):
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'to_month' is required and must be YYYY-MM format."},
        )
    if to_month < from_month:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'to_month' must be >= 'from_month'."},
        )
    if _month_diff(from_month, to_month) > _MAX_RANGE_MONTHS:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"Date range must not exceed {_MAX_RANGE_MONTHS} months."},
        )

    mgmt_fee = _parse_mgmt_fee(management_fee_pct)
    if mgmt_fee is None:
        return make_error_response(
            status_code=400, code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'management_fee_pct' must be between 0.0 and 100.0."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch all rows in range in one query
        range_start, _ = _month_start_end(from_month)
        _, range_end   = _month_start_end(to_month)

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .gte("recorded_at", range_start)
            .lt("recorded_at", range_end)
            .order("recorded_at", desc=False)
            .execute()
        )
        all_rows: List[dict] = result.data or []

        if not all_rows:
            return make_error_response(
                status_code=404, code=ErrorCode.PROPERTY_NOT_FOUND,
                extra={"property_id": property_id, "from_month": from_month, "to_month": to_month},
            )

        # Bucket rows by month
        months = _months_between(from_month, to_month)
        monthly_summaries: List[Dict[str, Any]] = []

        for month in months:
            m_start, m_end = _month_start_end(month)
            month_rows = [
                r for r in all_rows
                if r.get("recorded_at", "") >= m_start and r.get("recorded_at", "") < m_end
            ]
            summary = _build_month_summary(month_rows, month, mgmt_fee)
            monthly_summaries.append(summary)

        totals = _aggregate_months(monthly_summaries)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":    tenant_id,
                "property_id":  property_id,
                "from_month":   from_month,
                "to_month":     to_month,
                "management_fee_pct": _fmt(mgmt_fee),
                "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "totals":    totals,
                "monthly":   monthly_summaries,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /revenue-report/%s error: %s", property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
