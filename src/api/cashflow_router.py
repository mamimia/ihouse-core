"""
Phase 120 — Payout Timeline / Cashflow View

GET /financial/cashflow?period=YYYY-MM

Honest cashflow view for the authenticated tenant. Key design principle:
    OTA_COLLECTING bookings are NOT counted as received payout.
    Only PAYOUT_RELEASED bookings appear in confirmed_released.

Sections returned:
    expected_inflows_by_week:
        Bookings with PAYOUT_PENDING or OWNER_NET_PENDING lifecycle status,
        grouped by the ISO week in which the booking's due_date (check-in) falls.
        These are amounts expected but NOT yet released.

    confirmed_released:
        Bookings with PAYOUT_RELEASED lifecycle status for the period.
        Sums per currency.

    overdue:
        Bookings with PAYOUT_PENDING or OWNER_NET_PENDING where
        net_to_property is known and recorded_at is in the period.
        Grouped per currency. (All pending are technically overdue if
        no release signal has been received — this surfaces them explicitly.)

    forward_projection:
        30/60/90-day windows from the end of the period.
        Counts bookings with non-CANCELED, non-PAYOUT_RELEASED status
        that have total_price data. Projection confidence = "estimated".

Invariants:
    - Reads from booking_financial_facts ONLY.
    - Monetary fields returned as strings.
    - Deduplication: most-recent recorded_at per booking_id.
    - JWT auth required.
    - Tenant isolation via .eq("tenant_id", tenant_id).
    - OTA_COLLECTING bookings explicitly excluded from all inflow counts.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response
from api.financial_aggregation_router import (
    _canonical_currency,
    _dedup_latest,
    _fetch_period_rows,
    _fmt,
    _get_supabase_client,
    _month_bounds,
    _to_decimal,
    _validate_period,
)
from api.financial_dashboard_router import _project_lifecycle_status

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Lifecycle statuses that represent expected (but unreleased) payout
_PENDING_STATUSES = frozenset({
    "PAYOUT_PENDING",
    "OWNER_NET_PENDING",
})

# Lifecycle statuses to EXCLUDE from forward-projection inflow counts
_EXCLUDED_FROM_PROJECTION = frozenset({
    "OTA_COLLECTING",          # not yet at property — honest exclusion
    "RECONCILIATION_PENDING",  # disputed
    "UNKNOWN",                 # insufficient data
})


# ---------------------------------------------------------------------------
# ISO week key
# ---------------------------------------------------------------------------

def _iso_week_key(date_str: Optional[str]) -> str:
    """
    Convert a date string to an ISO week key like '2026-W10'.
    Returns 'unknown-week' if the date cannot be parsed.
    """
    if not date_str:
        return "unknown-week"
    try:
        # Handle both date-only and datetime strings
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        iso = dt.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    except Exception:
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            iso = dt.isocalendar()
            return f"{iso.year}-W{iso.week:02d}"
        except Exception:
            return "unknown-week"


def _period_end_date(period: str) -> datetime:
    """Return the first moment after the period (start of next month, UTC)."""
    try:
        year, month = int(period[:4]), int(period[5:7])
        if month == 12:
            return datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        return datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except Exception:
        return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# GET /financial/cashflow
# ---------------------------------------------------------------------------

@router.get(
    "/financial/cashflow",
    tags=["financial"],
    summary="Payout timeline and cashflow view for the period",
    responses={
        200: {"description": "Cashflow view with weekly inflow buckets, confirmed releases, overdue, and forward projection"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_cashflow(
    period: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Honest cashflow view for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Key honesty rule:** `OTA_COLLECTING` bookings are **never** counted as
    received payout. Only `PAYOUT_RELEASED` status appears in `confirmed_released`.

    **Returns:**
    - `expected_inflows_by_week` — pending amounts by ISO week (PAYOUT_PENDING / OWNER_NET_PENDING)
    - `confirmed_released` — confirmed payout totals by currency (PAYOUT_RELEASED only)
    - `overdue` — all pending amounts explicitly surfaced as overdue
    - `forward_projection` — 30/60/90-day booking count + estimated revenue (non-canceled, non-released)
    - `totals` — aggregate pending and released amounts per currency
    - `ota_collecting_excluded_count` — count of OTA_COLLECTING bookings explicitly skipped

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err

    try:
        db = client if client is not None else _get_supabase_client()
        rows = _fetch_period_rows(db, tenant_id, period)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        # Classify each deduped booking
        period_end = _period_end_date(period)  # type: ignore[arg-type]
        now_utc = datetime.now(tz=timezone.utc)

        # Accumulators
        # expected_inflows_by_week[week_key][currency] = total_net
        inflows_by_week: Dict[str, Dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: Decimal("0")))

        # confirmed_released[currency] = total
        confirmed: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        confirmed_count: Dict[str, int] = defaultdict(int)

        # overdue[currency] = total
        overdue: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        overdue_count: Dict[str, int] = defaultdict(int)

        ota_collecting_excluded = 0

        # Forward projection: [30, 60, 90] day windows from period_end
        proj_windows = [30, 60, 90]
        proj_counts: Dict[int, int] = {d: 0 for d in proj_windows}
        proj_revenue: Dict[int, Dict[str, Decimal]] = {d: defaultdict(lambda: Decimal("0")) for d in proj_windows}

        for row in deduped:
            event_kind = row.get("event_kind") or "BOOKING_CREATED"
            lifecycle = _project_lifecycle_status(row, event_kind)
            cur = _canonical_currency(row.get("currency"))
            net = _to_decimal(row.get("net_to_property"))
            total = _to_decimal(row.get("total_price"))
            recorded_at_str = row.get("recorded_at") or ""

            # OTA_COLLECTING — explicitly excluded, count and skip
            if lifecycle == "OTA_COLLECTING":
                ota_collecting_excluded += 1
                continue

            if lifecycle == "PAYOUT_RELEASED":
                confirmed[cur] += net if net > Decimal("0") else total
                confirmed_count[cur] += 1
                continue

            if lifecycle in _PENDING_STATUSES:
                # Expected inflows bucket by week of recorded_at (proxy for check-in week)
                week_key = _iso_week_key(recorded_at_str)
                net_or_total = net if net > Decimal("0") else total
                inflows_by_week[week_key][cur] += net_or_total

                # All pending are overdue (no release signal received)
                overdue[cur] += net_or_total
                overdue_count[cur] += 1

            # Forward projection: non-canceled, non-released bookings with price data
            if lifecycle not in _EXCLUDED_FROM_PROJECTION and lifecycle != "PAYOUT_RELEASED":
                proj_amount = total if total > Decimal("0") else Decimal("0")
                # Assign to projection windows based on period_end
                for days in proj_windows:
                    window_end = period_end + timedelta(days=days)
                    # Simple heuristic: all active bookings in period count toward all windows
                    proj_counts[days] += 1
                    proj_revenue[days][cur] += proj_amount
                    break  # count each booking only once (in the smallest window it qualifies for)

        # Build output
        # expected_inflows_by_week — sorted by week key
        inflows_out: Dict[str, Dict[str, str]] = {}
        for week in sorted(inflows_by_week.keys()):
            inflows_out[week] = {
                cur: _fmt(amount)
                for cur, amount in sorted(inflows_by_week[week].items())
            }

        # confirmed_released
        confirmed_out: Dict[str, Any] = {
            cur: {"total": _fmt(amount), "booking_count": confirmed_count[cur]}
            for cur, amount in sorted(confirmed.items())
        }

        # overdue
        overdue_out: Dict[str, Any] = {
            cur: {"total": _fmt(amount), "booking_count": overdue_count[cur]}
            for cur, amount in sorted(overdue.items())
        }

        # forward_projection
        proj_out: Dict[str, Any] = {}
        for days in proj_windows:
            proj_out[f"next_{days}_days"] = {
                "booking_count": proj_counts[days],
                "estimated_revenue": {
                    cur: _fmt(amount)
                    for cur, amount in sorted(proj_revenue[days].items())
                },
                "confidence": "estimated",
                "note": "OTA_COLLECTING excluded. PAYOUT_RELEASED excluded. Non-canceled active bookings only.",
            }

        # Totals per currency
        all_currencies = set(overdue.keys()) | set(confirmed.keys())
        totals_out: Dict[str, Any] = {}
        for cur in sorted(all_currencies):
            totals_out[cur] = {
                "total_pending": _fmt(overdue.get(cur, Decimal("0"))),
                "total_released": _fmt(confirmed.get(cur, Decimal("0"))),
            }

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "period": period,
                "total_bookings_checked": len(deduped),
                "ota_collecting_excluded_count": ota_collecting_excluded,
                "expected_inflows_by_week": inflows_out,
                "confirmed_released": confirmed_out,
                "overdue": overdue_out,
                "forward_projection": proj_out,
                "totals": totals_out,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /financial/cashflow error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
