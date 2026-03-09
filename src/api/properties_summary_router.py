"""
Phase 130 — Properties Summary Dashboard

Provides a per-property operational summary for the authenticated tenant:
  - active_count: how many ACTIVE bookings per property
  - canceled_count: how many CANCELED bookings per property
  - next_check_in: earliest upcoming check_in date among ACTIVE bookings
  - next_check_out: earliest upcoming check_out date among ACTIVE bookings
  - has_conflict: True if any two ACTIVE bookings share at least one date

This is a dashboard-level aggregation — operators see their entire portfolio
at a glance without having to query per-property.

Endpoint:
    GET /properties/summary

Query parameters:
    - limit (int, optional, 1–200, default 100): max properties returned

Invariants:
    - Reads from booking_state only. Never reads event_log directly.
    - Never reads booking_financial_facts or tasks.
    - Zero write-path changes.
    - JWT auth required (tenant-scoped).
    - Properties are sorted by property_id (stable ordering).
    - Only properties that have at least one booking (ACTIVE or CANCELED) appear.
    - "today" for next_check_in/next_check_out calculations is UTC date.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from itertools import combinations
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_LIMIT = 200
_DEFAULT_LIMIT = 100


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Conflict detection helper (reused from Phase 128 pattern, pure Python)
# ---------------------------------------------------------------------------

def _has_active_conflict(active_bookings: List[Dict[str, Any]]) -> bool:
    """
    Returns True if any two ACTIVE bookings in the list share at least one date.
    check_in inclusive, check_out exclusive.
    """
    booking_dates: List[Set[date]] = []
    for b in active_bookings:
        ci_str = b.get("canonical_check_in") or b.get("check_in") or ""
        co_str = b.get("canonical_check_out") or b.get("check_out") or ""
        try:
            ci = date.fromisoformat(ci_str)
            co = date.fromisoformat(co_str)
        except (ValueError, TypeError):
            continue
        dates: Set[date] = set()
        cur = ci
        while cur < co:
            dates.add(cur)
            cur += timedelta(days=1)
        if dates:
            booking_dates.append(dates)

    for dates_a, dates_b in combinations(booking_dates, 2):
        if dates_a & dates_b:
            return True
    return False


# ---------------------------------------------------------------------------
# Per-property summary builder
# ---------------------------------------------------------------------------

def _build_property_summary(
    property_id: str,
    bookings: List[Dict[str, Any]],
    today: date,
) -> Dict[str, Any]:
    """
    Build summary record for one property from its booking rows.
    """
    active = [b for b in bookings if (b.get("lifecycle_status") or b.get("status", "")).upper() in ("ACTIVE", "active")]
    canceled = [b for b in bookings if (b.get("lifecycle_status") or b.get("status", "")).upper() in ("CANCELED", "canceled")]

    # next_check_in: earliest future (or today) check_in from ACTIVE bookings
    next_check_in: Optional[str] = None
    min_ci: Optional[date] = None
    for b in active:
        ci_str = b.get("canonical_check_in") or b.get("check_in") or ""
        try:
            ci = date.fromisoformat(ci_str)
            if ci >= today:
                if min_ci is None or ci < min_ci:
                    min_ci = ci
        except (ValueError, TypeError):
            pass
    if min_ci is not None:
        next_check_in = min_ci.isoformat()

    # next_check_out: earliest future check_out from ACTIVE bookings
    next_check_out: Optional[str] = None
    min_co: Optional[date] = None
    for b in active:
        co_str = b.get("canonical_check_out") or b.get("check_out") or ""
        try:
            co = date.fromisoformat(co_str)
            if co > today:
                if min_co is None or co < min_co:
                    min_co = co
        except (ValueError, TypeError):
            pass
    if min_co is not None:
        next_check_out = min_co.isoformat()

    conflict = _has_active_conflict(active)

    return {
        "property_id": property_id,
        "active_count": len(active),
        "canceled_count": len(canceled),
        "next_check_in": next_check_in,
        "next_check_out": next_check_out,
        "has_conflict": conflict,
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/properties/summary",
    tags=["properties"],
    summary="Properties Summary Dashboard (Phase 130)",
    description=(
        "Per-property operational summary for the authenticated tenant.\n\n"
        "Returns one record per property (that has at least one booking) showing:\n"
        "- `active_count`: number of ACTIVE bookings\n"
        "- `canceled_count`: number of CANCELED bookings\n"
        "- `next_check_in`: earliest upcoming check-in date among ACTIVE bookings\n"
        "- `next_check_out`: earliest upcoming check-out date among ACTIVE bookings\n"
        "- `has_conflict`: True if two or more ACTIVE bookings overlap\n\n"
        "**Source:** `booking_state` — read-only. Never writes.\n\n"
        "**Ordering:** Properties sorted by `property_id` (stable).\n\n"
        "**Limit:** 1–200 properties, default 100."
    ),
    responses={
        200: {"description": "Per-property summary for this tenant's portfolio."},
        400: {"description": "Invalid limit parameter."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_properties_summary(
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /properties/summary

    Returns per-property operational summary for the authenticated tenant.

    Authentication: Bearer JWT required. tenant_id from sub claim.

    Query parameters:
        limit (optional, 1-200, default 100): maximum number of properties.

    Source: booking_state. Read-only. Zero write-path changes.
    """
    # Clamp limit
    if limit < 1 or limit > _MAX_LIMIT:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"limit must be between 1 and {_MAX_LIMIT}.",
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch all bookings for this tenant (ACTIVE + CANCELED)
        result = (
            db.table("booking_state")
            .select(
                "booking_id, property_id, lifecycle_status, status, "
                "canonical_check_in, canonical_check_out, check_in, check_out, "
                "tenant_id"
            )
            .eq("tenant_id", tenant_id)
            .execute()
        )
        rows = result.data or []

    except Exception:  # noqa: BLE001
        return make_error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Failed to query booking state.",
        )

    # Group by property_id
    by_property: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        pid = row.get("property_id", "")
        if pid:
            by_property.setdefault(pid, []).append(row)

    today = date.today()

    # Build summaries — sorted by property_id for stable ordering
    summaries = [
        _build_property_summary(pid, bookings, today)
        for pid, bookings in sorted(by_property.items())
    ]

    # Apply limit
    summaries = summaries[:limit]

    # Portfolio-level summary
    total_active = sum(s["active_count"] for s in summaries)
    total_canceled = sum(s["canceled_count"] for s in summaries)
    properties_with_conflicts = sum(1 for s in summaries if s["has_conflict"])

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "property_count": len(summaries),
            "portfolio": {
                "total_active_bookings": total_active,
                "total_canceled_bookings": total_canceled,
                "properties_with_conflicts": properties_with_conflicts,
            },
            "properties": summaries,
        },
    )
