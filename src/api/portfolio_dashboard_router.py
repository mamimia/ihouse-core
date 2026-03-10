"""
Phase 216 — Portfolio Dashboard UI (Backend API)

Single endpoint that provides the full cross-property owner portfolio view.
Consolidates: occupancy, revenue, pending tasks, and sync health per property.

Endpoint:
    GET /portfolio/dashboard
        Returns one summary card per property found for this tenant.
        Optionally filtered by `as_of` date (for occupancy), `month` (for revenue).

Data sources (all read-only, tenant-scoped):
    occupancy   → booking_state (active bookings per property)
    revenue     → booking_financial_facts (current month gross/net aggregation)
    tasks       → tasks table (pending/in_progress count per property)
    sync_health → outbound_sync_log (last sync attempt per property, lag in hours)

Design:
    - Single DB round: 4 parallel data queries, merged in memory per property_id.
    - Never raises — each section degrades gracefully (returns null/0s on error).
    - Property list is derived from union of all four data sources.
    - Sorted: properties with most urgent signals first
      (has_stale_sync DESC, pending_tasks DESC, active_bookings DESC).
    - No new tables. Pure read from existing infrastructure.

Invariants:
    - JWT auth required.
    - Tenant isolation on all queries.
    - Revenue: current calendar month (YYYY-MM) by default, overridable via `month`.
    - Sync health: `stale` if last sync > 24h ago (same threshold as Phase 127).
    - Occupancy: today's active bookings count + arrivals_today + departures_today.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from api.financial_aggregation_router import (
    _dedup_latest,
    _fmt,
    _to_decimal,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["portfolio"])

_STALE_SYNC_HOURS = 24


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Data fetchers (each returns raw rows — never raises, returns [] on error)
# ---------------------------------------------------------------------------

def _fetch_occupancy(db: Any, tenant_id: str, today: str) -> List[dict]:
    """Fetch all active bookings for this tenant today."""
    try:
        result = (
            db.table("booking_state")
            .select("property_id, booking_id, check_in, check_out, status")
            .eq("tenant_id", tenant_id)
            .eq("status", "active")
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_occupancy error: %s", exc)
        return []


def _fetch_revenue(db: Any, tenant_id: str, month: str) -> List[dict]:
    """Fetch booking_financial_facts rows for the given month."""
    try:
        year, mon = int(month[:4]), int(month[5:7])
        m_start = f"{year:04d}-{mon:02d}-01T00:00:00"
        m_end = f"{year:04d}-{mon + 1:02d}-01T00:00:00" if mon < 12 else f"{year + 1:04d}-01-01T00:00:00"
        result = (
            db.table("booking_financial_facts")
            .select("property_id, booking_id, total_price, net_to_property, currency, recorded_at, event_kind, canonical_status, payout_status")
            .eq("tenant_id", tenant_id)
            .gte("recorded_at", m_start)
            .lt("recorded_at", m_end)
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_revenue error: %s", exc)
        return []


def _fetch_tasks(db: Any, tenant_id: str) -> List[dict]:
    """Fetch open (pending/in_progress) tasks for this tenant."""
    try:
        result = (
            db.table("tasks")
            .select("property_id, task_id, status, escalation_level")
            .eq("tenant_id", tenant_id)
            .in_("status", ["pending", "in_progress"])
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_tasks error: %s", exc)
        return []


def _fetch_sync_health(db: Any, tenant_id: str) -> List[dict]:
    """Fetch most-recent outbound sync log row per property."""
    try:
        result = (
            db.table("outbound_sync_log")
            .select("property_id, provider, status, executed_at, error_message")
            .eq("tenant_id", tenant_id)
            .order("executed_at", desc=True)
            .limit(500)
            .execute()
        )
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_sync_health error: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Per-property aggregation helpers
# ---------------------------------------------------------------------------

def _occupancy_for_property(rows: List[dict], property_id: str, today: str) -> Dict[str, Any]:
    prop_rows = [r for r in rows if r.get("property_id") == property_id]
    arrivals   = sum(1 for r in prop_rows if str(r.get("check_in") or "")  == today)
    departures = sum(1 for r in prop_rows if str(r.get("check_out") or "") == today)
    return {
        "active_bookings":   len(prop_rows),
        "arrivals_today":    arrivals,
        "departures_today":  departures,
        "cleanings_today":   departures,
    }


def _revenue_for_property(rows: List[dict], property_id: str) -> Dict[str, Any]:
    prop_rows = [r for r in rows if r.get("property_id") == property_id]
    if not prop_rows:
        return {"gross_total": None, "net_total": None, "currency": None, "booking_count": 0}
    deduped = _dedup_latest(prop_rows)
    currencies = {r.get("currency") for r in deduped if r.get("currency")}
    is_mixed = len(currencies) > 1
    currency = "MIXED" if is_mixed else next(iter(currencies), None)
    if is_mixed:
        return {"gross_total": None, "net_total": None, "currency": "MIXED", "booking_count": len(deduped)}
    gross_vals = [_to_decimal(r.get("total_price")) for r in deduped if r.get("total_price")]
    net_vals   = [_to_decimal(r.get("net_to_property")) for r in deduped if r.get("net_to_property")]
    gross_total = _fmt(sum((g for g in gross_vals if g), Decimal("0"))) if gross_vals else None
    net_total   = _fmt(sum((n for n in net_vals if n), Decimal("0"))) if net_vals else None
    return {
        "gross_total":   gross_total,
        "net_total":     net_total,
        "currency":      currency,
        "booking_count": len(deduped),
    }


def _tasks_for_property(rows: List[dict], property_id: str) -> Dict[str, Any]:
    prop_rows = [r for r in rows if r.get("property_id") == property_id]
    escalated = sum(1 for r in prop_rows if (r.get("escalation_level") or 0) > 0)
    return {
        "pending_tasks":   len(prop_rows),
        "escalated_tasks": escalated,
    }


def _sync_health_for_property(rows: List[dict], property_id: str, now_iso: str) -> Dict[str, Any]:
    prop_rows = [r for r in rows if r.get("property_id") == property_id]
    if not prop_rows:
        return {"last_sync_at": None, "last_sync_status": None, "stale": None, "provider_count": 0}

    # Most-recent sync per provider, then take the latest overall
    by_provider: Dict[str, dict] = {}
    for row in prop_rows:
        prov = row.get("provider") or "unknown"
        existing = by_provider.get(prov)
        if not existing or (row.get("executed_at") or "") > (existing.get("executed_at") or ""):
            by_provider[prov] = row

    latest = max(by_provider.values(), key=lambda r: r.get("executed_at") or "")
    last_sync_at = latest.get("executed_at")
    last_sync_status = latest.get("status")

    # Compute staleness: compare ISO strings (works for UTC timestamps)
    stale = None
    if last_sync_at:
        try:
            # Parse both as naive ISO — good enough for hours comparison
            delta_seconds = (
                datetime.fromisoformat(now_iso.replace("Z", ""))
                - datetime.fromisoformat(last_sync_at.replace("Z", "").replace("+00:00", ""))
            ).total_seconds()
            stale = delta_seconds > (_STALE_SYNC_HOURS * 3600)
        except Exception:  # noqa: BLE001
            stale = None

    return {
        "last_sync_at":     last_sync_at,
        "last_sync_status": last_sync_status,
        "stale":            stale,
        "provider_count":   len(by_provider),
    }


# ---------------------------------------------------------------------------
# GET /portfolio/dashboard
# ---------------------------------------------------------------------------

@router.get(
    "/portfolio/dashboard",
    tags=["portfolio"],
    summary="Portfolio Dashboard — cross-property owner view (Phase 216)",
    description=(
        "Consolidated per-property portfolio view for the authenticated tenant.\\n\\n"
        "Returns one card per property with:\\n"
        "- **Occupancy**: active bookings, today's arrivals/departures/cleanings\\n"
        "- **Revenue**: current-month gross/net from `booking_financial_facts`\\n"
        "- **Tasks**: pending + escalated task counts from `tasks`\\n"
        "- **Sync health**: last sync timestamp, staleness flag (>24h), per-provider count\\n\\n"
        "Properties are sorted by urgency: stale sync first, then most pending tasks, "
        "then most active bookings.\\n\\n"
        "Each section degrades gracefully — never returns an error for a missing sub-source."
    ),
    responses={
        200: {"description": "Portfolio dashboard — one card per property."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_portfolio_dashboard(
    as_of:  Optional[str] = Query(default=None, description="Override today's date (YYYY-MM-DD). Default: today UTC."),
    month:  Optional[str] = Query(default=None, description="Revenue month (YYYY-MM). Default: current month UTC."),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /portfolio/dashboard

    One aggregated card per property. Derived from 4 DB tables in parallel
    (in-memory merge — no cross-table JOINs in the DB).
    """
    try:
        now_utc  = datetime.now(tz=timezone.utc)
        today    = as_of if as_of else now_utc.strftime("%Y-%m-%d")
        cur_month = month if month else now_utc.strftime("%Y-%m")
        now_iso  = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        db = client if client is not None else _get_supabase_client()

        # Fetch all four data sources
        occ_rows  = _fetch_occupancy(db, tenant_id, today)
        rev_rows  = _fetch_revenue(db, tenant_id, cur_month)
        task_rows = _fetch_tasks(db, tenant_id)
        sync_rows = _fetch_sync_health(db, tenant_id)

        # Derive full property universe from all four sources
        property_ids: set = set()
        for rows in (occ_rows, rev_rows, task_rows, sync_rows):
            for r in rows:
                pid = r.get("property_id")
                if pid:
                    property_ids.add(pid)

        cards: List[Dict[str, Any]] = []
        for pid in property_ids:
            occ   = _occupancy_for_property(occ_rows, pid, today)
            rev   = _revenue_for_property(rev_rows, pid)
            tasks = _tasks_for_property(task_rows, pid)
            sync  = _sync_health_for_property(sync_rows, pid, now_iso)

            cards.append({
                "property_id": pid,
                "occupancy":   occ,
                "revenue":     {**rev, "month": cur_month},
                "tasks":       tasks,
                "sync_health": sync,
            })

        # Sort: stale_sync DESC, pending_tasks DESC, active_bookings DESC
        def _sort_key(c: dict) -> tuple:
            stale   = c["sync_health"].get("stale") or False
            tasks   = c["tasks"].get("pending_tasks") or 0
            active  = c["occupancy"].get("active_bookings") or 0
            return (-int(stale), -tasks, -active)

        cards.sort(key=_sort_key)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":     tenant_id,
                "as_of":         today,
                "revenue_month": cur_month,
                "generated_at":  now_iso,
                "property_count": len(cards),
                "properties":    cards,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /portfolio/dashboard error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
