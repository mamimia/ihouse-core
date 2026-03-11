"""
Phase 252 — Owner Financial Report API v2

Self-serve financial report endpoint for property owners.
Supports custom date ranges and drill-down by property, OTA, and booking.

Endpoints:
    GET /owner/financial-report
        Query params:
            date_from   (required, ISO date YYYY-MM-DD)
            date_to     (required, ISO date YYYY-MM-DD)
            property_id (optional — filter to one property)
            ota         (optional — filter to one OTA/channel)
            drill_down  (optional, enum: "property"|"ota"|"booking", default "property")
            page        (optional, int, default 1)
            page_size   (optional, int, default 50, max 200)

        Response:
            summary     { total_gross, total_net, total_commission, total_tax,
                          management_fee_total, booking_count, date_from, date_to }
            breakdown   [ { key, gross_revenue, net_revenue, commission,
                            tax_amount, management_fee, booking_count } ]
            pagination  { page, page_size, total_count, has_more }
            exported_csv_url  null  (placeholder — future phase)

Data source: booking_financial_facts table (Phase 116+)
    Columns used: property_id, tenant_id, ota_name, booking_ref,
                  gross_revenue, net_revenue, commission, tax_amount,
                  management_fee, check_in (for date filtering)

Design:
    - JWT required, tenant_id from token sub
    - date_from / date_to filter on check_in date
    - drill_down="property"  → group by property_id
    - drill_down="ota"       → group by ota_name
    - drill_down="booking"   → individual bookings (paginated)
    - Management fee sum included in all modes
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()

_DRILL_DOWN_OPTIONS = {"property", "ota", "booking"}
_MAX_PAGE_SIZE = 200


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _aggregate(rows: List[dict], group_key: str) -> List[dict]:
    """
    Aggregate a list of financial fact rows by group_key.
    Returns list sorted descending by gross_revenue.
    """
    totals: dict[str, dict] = {}
    for row in rows:
        key = row.get(group_key) or "unknown"
        if key not in totals:
            totals[key] = {
                "key": key,
                "gross_revenue": 0.0,
                "net_revenue": 0.0,
                "commission": 0.0,
                "tax_amount": 0.0,
                "management_fee": 0.0,
                "booking_count": 0,
            }
        t = totals[key]
        t["gross_revenue"] += float(row.get("gross_revenue") or 0)
        t["net_revenue"] += float(row.get("net_revenue") or 0)
        t["commission"] += float(row.get("commission") or 0)
        t["tax_amount"] += float(row.get("tax_amount") or 0)
        t["management_fee"] += float(row.get("management_fee") or 0)
        t["booking_count"] += 1

    result = sorted(totals.values(), key=lambda x: x["gross_revenue"], reverse=True)
    # Round all floats to 2dp
    for r in result:
        for k in ("gross_revenue", "net_revenue", "commission", "tax_amount", "management_fee"):
            r[k] = round(r[k], 2)
    return result


def _summary(rows: List[dict], date_from: str, date_to: str) -> dict:
    summary = {
        "date_from": date_from,
        "date_to": date_to,
        "booking_count": len(rows),
        "total_gross": round(sum(float(r.get("gross_revenue") or 0) for r in rows), 2),
        "total_net": round(sum(float(r.get("net_revenue") or 0) for r in rows), 2),
        "total_commission": round(sum(float(r.get("commission") or 0) for r in rows), 2),
        "total_tax": round(sum(float(r.get("tax_amount") or 0) for r in rows), 2),
        "management_fee_total": round(sum(float(r.get("management_fee") or 0) for r in rows), 2),
    }
    return summary


# ---------------------------------------------------------------------------
# GET /owner/financial-report
# ---------------------------------------------------------------------------

@router.get(
    "/owner/financial-report",
    tags=["owner"],
    summary="Owner financial report v2 — custom date range with drill-down",
    responses={
        200: {"description": "Financial report data"},
        400: {"description": "Missing or invalid query parameters"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_owner_financial_report(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    property_id: Optional[str] = None,
    ota: Optional[str] = None,
    drill_down: str = "property",
    page: int = 1,
    page_size: int = 50,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Self-serve owner financial report for a tenant.

    **Required:** `date_from` and `date_to` (ISO dates, e.g. 2026-01-01).

    **drill_down options:**
    - `property` — aggregate by property
    - `ota`      — aggregate by OTA/channel
    - `booking`  — raw booking list (paginated)

    **Authentication:** Bearer JWT. `sub` = `tenant_id`.
    """
    # Validate required params
    if not date_from or not date_to:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="date_from and date_to are required (YYYY-MM-DD).",
        )
    if date_from > date_to:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="date_from must be on or before date_to.",
        )
    if drill_down not in _DRILL_DOWN_OPTIONS:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"drill_down must be one of: {', '.join(sorted(_DRILL_DOWN_OPTIONS))}.",
        )
    page_size = min(max(1, page_size), _MAX_PAGE_SIZE)
    page = max(1, page)

    try:
        db = _client if _client is not None else _get_supabase_client()

        # Base query
        q = (
            db.table("booking_financial_facts")
            .select(
                "property_id, ota_name, booking_ref, gross_revenue, "
                "net_revenue, commission, tax_amount, management_fee, check_in"
            )
            .eq("tenant_id", tenant_id)
            .gte("check_in", date_from)
            .lte("check_in", date_to)
        )
        if property_id:
            q = q.eq("property_id", property_id)
        if ota:
            q = q.eq("ota_name", ota)

        result = q.execute()
        rows: List[dict] = result.data or []

        # Summary (always over full result)
        smry = _summary(rows, date_from, date_to)

        # Breakdown by drill_down mode
        if drill_down == "property":
            breakdown = _aggregate(rows, "property_id")
            total_count = len(breakdown)
            offset = (page - 1) * page_size
            breakdown = breakdown[offset: offset + page_size]

        elif drill_down == "ota":
            breakdown = _aggregate(rows, "ota_name")
            total_count = len(breakdown)
            offset = (page - 1) * page_size
            breakdown = breakdown[offset: offset + page_size]

        else:  # booking (raw, paginated)
            total_count = len(rows)
            offset = (page - 1) * page_size
            page_rows = rows[offset: offset + page_size]
            breakdown = [
                {
                    "key": r.get("booking_ref", "?"),
                    "property_id": r.get("property_id"),
                    "ota_name": r.get("ota_name"),
                    "check_in": r.get("check_in"),
                    "gross_revenue": round(float(r.get("gross_revenue") or 0), 2),
                    "net_revenue": round(float(r.get("net_revenue") or 0), 2),
                    "commission": round(float(r.get("commission") or 0), 2),
                    "tax_amount": round(float(r.get("tax_amount") or 0), 2),
                    "management_fee": round(float(r.get("management_fee") or 0), 2),
                    "booking_count": 1,
                }
                for r in page_rows
            ]

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "drill_down": drill_down,
                "filters": {
                    "property_id": property_id,
                    "ota": ota,
                },
                "summary": smry,
                "breakdown": breakdown,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "has_more": (page * page_size) < total_count,
                },
                "exported_csv_url": None,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /owner/financial-report error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
