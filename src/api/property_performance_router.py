"""
Phase 243 — Property Performance Analytics API

GET /admin/properties/performance

Cross-property analytics dashboard combining:
  - booking_state (active/canceled counts per property)
  - booking_financial_facts (total_revenue, net_to_property per property)

This extends Phase 130 (properties summary — operational) with financial
performance data, giving managers a full picture of each property's
booking volume AND revenue health.

Response shape:
    {
        "tenant_id": "...",
        "generated_at": "...",
        "property_count": 3,
        "portfolio_totals": {
            "total_active_bookings": 42,
            "total_canceled_bookings": 10,
            "total_gross_revenue": "152340.00",
            "total_net_revenue": "130000.00",
            "currencies": ["THB"]
        },
        "properties": [
            {
                "property_id": "prop_a",
                "active_bookings": 15,
                "canceled_bookings": 3,
                "total_gross_revenue": {"THB": "54200.00"},
                "total_net_revenue": {"THB": "45000.00"},
                "avg_booking_value": {"THB": "3613.33"},
                "cancellation_rate_pct": 16.7,
                "top_provider": "airbnb"
            }
        ]
    }

Invariants:
    - Reads booking_state and booking_financial_facts ONLY.
    - Never writes. Never bypasses apply_envelope.
    - Tenant isolation via .eq("tenant_id", tenant_id).
    - JWT auth required.
    - All monetary values as strings (Decimal precision preserved).
    - No period filter — all-time performance snapshot.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Data reads
# ---------------------------------------------------------------------------

def _read_booking_state(db: Any, tenant_id: str) -> List[dict]:
    """Read all booking_state rows for the tenant. Never raises."""
    try:
        result = (
            db.table("booking_state")
            .select("booking_id, property_id, source, status")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return result.data or []
    except Exception:  # noqa: BLE001
        logger.exception("property_performance_router: failed to read booking_state")
        return []


def _read_financial_facts(db: Any, tenant_id: str) -> List[dict]:
    """
    Read the latest financial fact row per booking from booking_financial_facts.
    Returns list of {booking_id, property_id, currency, total_price, net_to_property}.
    Never raises.
    """
    try:
        result = (
            db.table("booking_financial_facts")
            .select(
                "booking_id, property_id, currency, total_price, net_to_property, "
                "recorded_at"
            )
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception:  # noqa: BLE001
        logger.exception("property_performance_router: failed to read booking_financial_facts")
        return []


# ---------------------------------------------------------------------------
# Deduplication — latest recorded_at per booking_id
# ---------------------------------------------------------------------------

def _dedup_latest_financial(rows: List[dict]) -> List[dict]:
    """Keep only the most recent financial row per booking_id."""
    seen: set = set()
    result = []
    for row in rows:
        bid = row.get("booking_id")
        if bid and bid not in seen:
            seen.add(bid)
            result.append(row)
    return result


# ---------------------------------------------------------------------------
# Monetary helpers
# ---------------------------------------------------------------------------

def _to_decimal(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _fmt(v: Decimal) -> str:
    return f"{v:.2f}"


# ---------------------------------------------------------------------------
# Per-property aggregator
# ---------------------------------------------------------------------------

def _build_property_record(
    property_id: str,
    state_rows: List[dict],
    financial_rows: List[dict],
) -> Dict[str, Any]:
    """
    Build a performance record for a single property.

    state_rows: booking_state rows for this property
    financial_rows: deduplicated booking_financial_facts rows for this property
    """
    # Booking counts from state
    active = sum(1 for r in state_rows if (r.get("status") or "").lower() == "active")
    canceled = sum(1 for r in state_rows if (r.get("status") or "").lower() == "canceled")
    total_bs = active + canceled

    cancellation_rate = (
        round(canceled / total_bs * 100, 1) if total_bs > 0 else None
    )

    # Top provider (most bookings by source)
    provider_counts: Dict[str, int] = {}
    for r in state_rows:
        src = r.get("source") or "unknown"
        provider_counts[src] = provider_counts.get(src, 0) + 1
    top_provider: Optional[str] = (
        max(provider_counts, key=lambda k: provider_counts[k])
        if provider_counts
        else None
    )

    # Revenue from financial facts — grouped by currency
    gross_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    net_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for r in financial_rows:
        cur = (r.get("currency") or "UNKNOWN").upper()
        gross_by_cur[cur] += _to_decimal(r.get("total_price"))
        net_by_cur[cur] += _to_decimal(r.get("net_to_property"))

    total_gross = {c: _fmt(v) for c, v in gross_by_cur.items()}
    total_net = {c: _fmt(v) for c, v in net_by_cur.items()}

    # Average booking value per currency (gross / active bookings)
    avg_booking: Dict[str, str] = {}
    for cur, gross in gross_by_cur.items():
        if active > 0:
            avg_booking[cur] = _fmt(gross / active)
        else:
            avg_booking[cur] = _fmt(gross)

    return {
        "property_id": property_id,
        "active_bookings": active,
        "canceled_bookings": canceled,
        "total_gross_revenue": total_gross,
        "total_net_revenue": total_net,
        "avg_booking_value": avg_booking,
        "cancellation_rate_pct": cancellation_rate,
        "top_provider": top_provider,
    }


# ---------------------------------------------------------------------------
# Portfolio totals builder
# ---------------------------------------------------------------------------

def _build_portfolio_totals(properties: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate portfolio-level counters and revenue totals."""
    total_active = sum(p["active_bookings"] for p in properties)
    total_canceled = sum(p["canceled_bookings"] for p in properties)

    # Collapse per-currency gross revenue
    all_gross: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    all_net: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for p in properties:
        for cur, val in p["total_gross_revenue"].items():
            all_gross[cur] += _to_decimal(val)
        for cur, val in p["total_net_revenue"].items():
            all_net[cur] += _to_decimal(val)

    currencies = sorted(set(all_gross) | set(all_net))

    return {
        "total_active_bookings": total_active,
        "total_canceled_bookings": total_canceled,
        "gross_revenue_by_currency": {c: _fmt(all_gross[c]) for c in currencies},
        "net_revenue_by_currency": {c: _fmt(all_net[c]) for c in currencies},
        "currencies": currencies,
    }


# ---------------------------------------------------------------------------
# GET /admin/properties/performance
# ---------------------------------------------------------------------------

@router.get(
    "/admin/properties/performance",
    tags=["admin"],
    summary="Per-property performance analytics: bookings + revenue",
    responses={
        200: {"description": "Per-property booking counts and revenue totals"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_performance(
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Cross-property performance analytics dashboard.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **No query parameters required** — all-time performance snapshot.

    **Returns:**
    - `property_count` — number of properties with any booking activity
    - `portfolio_totals` — aggregate active/canceled counts + revenue by currency
    - `properties` — per-property record sorted by active_bookings descending:
        - `active_bookings`, `canceled_bookings`, `cancellation_rate_pct`
        - `total_gross_revenue`, `total_net_revenue`, `avg_booking_value` (per currency)
        - `top_provider` — OTA with most bookings for this property

    **Sources:** `booking_state` (counts) + `booking_financial_facts` (revenue).
    """
    from datetime import datetime, timezone

    generated_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        state_rows = _read_booking_state(db, tenant_id)
        financial_rows_raw = _read_financial_facts(db, tenant_id)
        financial_rows = _dedup_latest_financial(financial_rows_raw)

        # Group state rows by property_id
        state_by_prop: Dict[str, List[dict]] = {}
        for r in state_rows:
            pid = r.get("property_id") or "unknown"
            state_by_prop.setdefault(pid, []).append(r)

        # Group financial rows by property_id
        fin_by_prop: Dict[str, List[dict]] = {}
        for r in financial_rows:
            pid = r.get("property_id") or "unknown"
            fin_by_prop.setdefault(pid, []).append(r)

        # Union of all property_ids from both sources
        all_props = sorted(set(state_by_prop) | set(fin_by_prop))

        properties = [
            _build_property_record(
                property_id=pid,
                state_rows=state_by_prop.get(pid, []),
                financial_rows=fin_by_prop.get(pid, []),
            )
            for pid in all_props
        ]

        # Sort: most active bookings first, then alphabetical property_id
        properties.sort(key=lambda x: (-x["active_bookings"], x["property_id"]))

        portfolio = _build_portfolio_totals(properties)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "generated_at": generated_at,
                "property_count": len(properties),
                "portfolio_totals": portfolio,
                "properties": properties,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/properties/performance error for tenant=%s: %s",
            tenant_id,
            exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
