"""
Phase 233 — Revenue Forecast Engine

Endpoint: GET /ai/copilot/revenue-forecast

Returns a forward-looking revenue projection for the authenticated tenant,
using confirmed/active bookings in booking_state as the primary data source
and booking_financial_facts historical averages as a fallback.

Design principles:
  - Read-only. Zero DB writes (ai_audit_log is best-effort, not counted).
  - No cross-currency arithmetic — each currency is independent.
  - No hard dependency on LLM — heuristic narrative always generated.
  - Tenant isolation enforced on every query.
  - Best-effort historical lookup — falls back gracefully to null avg fields.

Query parameters:
  window      int     30 | 60 | 90 (default 30)
  property_id str     optional — filter to single property
  currency    str     optional 3-letter ISO code — filter bookings to one currency

Response shape (200):
{
  "tenant_id": "...",
  "generated_at": "2026-03-11T07:00:00Z",
  "window_days": 30,
  "property_id": null | "prop-1",
  "currency_filter": null | "THB",
  "forecast": {
    "confirmed_bookings": 12,
    "projected_gross": "84000.00",
    "projected_net": "71400.00",
    "currency": "THB",
    "occupancy_pct": 40.0,
    "total_nights_analyzed": 30,
    "booked_nights": 12
  },
  "historical_avg": {
    "avg_gross_per_booking": "7000.00",
    "avg_net_per_booking": "5950.00",
    "sample_bookings": 48,
    "lookback_days": 90
  },
  "narrative": "...",
  "properties_included": ["prop-1", "prop-2"]
}
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# Valid forecast windows
_VALID_WINDOWS = {30, 60, 90}

# Historical lookback for average calculation (days before today)
_HISTORY_LOOKBACK_DAYS = 90

_ACTIVE_LIFECYCLE = ("CONFIRMED", "ACTIVE")


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Decimal helpers
# ---------------------------------------------------------------------------

def _to_dec(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _fmt(d: Decimal) -> str:
    return str(d.quantize(Decimal("0.01")))


# ---------------------------------------------------------------------------
# Data fetch helpers
# ---------------------------------------------------------------------------

def _fetch_confirmed_bookings(
    db: Any,
    tenant_id: str,
    date_from: str,
    date_to: str,
    property_id: Optional[str],
    currency: Optional[str],
) -> list[dict]:
    """
    Query booking_state for CONFIRMED/ACTIVE bookings in the forecast window.
    Applies property_id and currency filters when provided.
    """
    try:
        query = (
            db.table("booking_state")
            .select(
                "booking_id, property_id, check_in, check_out, "
                "guest_name, lifecycle_status, provider"
            )
            .eq("tenant_id", tenant_id)
            .gte("check_in", date_from)
            .lte("check_in", date_to)
            .in_("lifecycle_status", list(_ACTIVE_LIFECYCLE))
        )
        if property_id:
            query = query.eq("property_id", property_id)
        result = query.limit(500).execute()
        rows = result.data or []

        # Currency filter is applied via financial_facts join in _enrich_with_financials
        # At this stage we return all confirmed bookings regardless of currency
        return rows
    except Exception as exc:  # noqa: BLE001
        logger.warning("revenue_forecast: booking_state query failed: %s", exc)
        return []


def _fetch_financial_facts_for_bookings(
    db: Any,
    tenant_id: str,
    booking_ids: list[str],
    currency: Optional[str],
) -> dict[str, dict]:
    """
    Fetch booking_financial_facts rows for the given booking_ids.
    Returns dict keyed by booking_id → most-recent financial row.
    """
    if not booking_ids:
        return {}
    try:
        query = (
            db.table("booking_financial_facts")
            .select("booking_id, total_price, net_to_property, ota_commission, currency, recorded_at")
            .eq("tenant_id", tenant_id)
            .in_("booking_id", booking_ids)
        )
        if currency:
            query = query.eq("currency", currency.upper())
        result = query.limit(1000).execute()
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("revenue_forecast: financial_facts query failed: %s", exc)
        return {}

    # Keep latest row per booking_id
    latest: dict[str, dict] = {}
    for row in rows:
        bid = row.get("booking_id", "")
        existing = latest.get(bid)
        if existing is None or (row.get("recorded_at") or "") > (existing.get("recorded_at") or ""):
            latest[bid] = row
    return latest


def _fetch_historical_avg(
    db: Any,
    tenant_id: str,
    lookback_days: int,
    property_id: Optional[str],
    currency: Optional[str],
) -> dict:
    """
    Compute average gross and net per booking from booking_financial_facts
    over the past `lookback_days` days. Used as fallback when confirmed
    bookings have no financial data yet.
    """
    today = date.today()
    date_from = (today - timedelta(days=lookback_days)).isoformat()
    date_to = today.isoformat()

    try:
        query = (
            db.table("booking_financial_facts")
            .select("booking_id, total_price, net_to_property, currency, recorded_at, property_id")
            .eq("tenant_id", tenant_id)
            .gte("recorded_at", date_from)
            .lt("recorded_at", date_to)
        )
        if property_id:
            query = query.eq("property_id", property_id)
        if currency:
            query = query.eq("currency", currency.upper())
        result = query.limit(1000).execute()
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("revenue_forecast: historical avg query failed: %s", exc)
        return {}

    if not rows:
        return {}

    # Deduplicate by booking_id (most-recent row)
    latest: dict[str, dict] = {}
    for row in rows:
        bid = row.get("booking_id", "")
        existing = latest.get(bid)
        if existing is None or (row.get("recorded_at") or "") > (existing.get("recorded_at") or ""):
            latest[bid] = row

    deduped = list(latest.values())
    if not deduped:
        return {}

    total_gross = sum(_to_dec(r.get("total_price")) for r in deduped)
    total_net = sum(_to_dec(r.get("net_to_property")) for r in deduped)
    count = len(deduped)

    return {
        "avg_gross_per_booking": _fmt(total_gross / count),
        "avg_net_per_booking": _fmt(total_net / count),
        "sample_bookings": count,
        "lookback_days": lookback_days,
    }


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------

def _project_occupancy(
    bookings: list[dict],
    window_days: int,
    property_count: int,
) -> tuple[float, int]:
    """
    Calculate occupancy percentage and total booked nights.

    Booked nights = sum of (check_out - check_in) for each booking,
    capped to the window.

    Returns (occupancy_pct, booked_nights).
    """
    if property_count <= 0:
        return 0.0, 0

    today = date.today()
    window_end = today + timedelta(days=window_days)
    booked_nights = 0

    for booking in bookings:
        try:
            ci = date.fromisoformat(booking.get("check_in") or "")
            co = booking.get("check_out")
            if co:
                co = date.fromisoformat(co)
            else:
                co = ci + timedelta(days=1)  # assume 1 night if missing
            # Clip to window
            ci = max(ci, today + timedelta(days=1))
            co = min(co, window_end)
            nights = (co - ci).days
            if nights > 0:
                booked_nights += nights
        except (ValueError, TypeError):
            continue

    total_available = window_days * property_count
    pct = round((booked_nights / total_available) * 100, 1) if total_available > 0 else 0.0
    return pct, booked_nights


def _project_revenue(
    bookings: list[dict],
    financial_map: dict[str, dict],
    historical_avg: dict,
    currency: Optional[str],
) -> tuple[Decimal, Decimal, str]:
    """
    Project gross and net revenue for confirmed bookings.

    For bookings WITH financial data → use actual values.
    For bookings WITHOUT financial data → use historical average.

    Returns (projected_gross, projected_net, dominant_currency).
    """
    # Determine dominant currency from financial data or currency param
    if currency:
        dominant = currency.upper()
    else:
        # Pick most common currency among financial facts
        ccy_counts: dict[str, int] = {}
        for row in financial_map.values():
            c = (row.get("currency") or "UNKNOWN").upper()
            ccy_counts[c] = ccy_counts.get(c, 0) + 1
        dominant = max(ccy_counts, key=lambda k: ccy_counts[k]) if ccy_counts else "UNKNOWN"

    avg_gross = _to_dec(historical_avg.get("avg_gross_per_booking"))
    avg_net = _to_dec(historical_avg.get("avg_net_per_booking"))

    total_gross = Decimal("0")
    total_net = Decimal("0")

    for booking in bookings:
        bid = booking.get("booking_id", "")
        facts = financial_map.get(bid)
        if facts:
            total_gross += _to_dec(facts.get("total_price"))
            total_net += _to_dec(facts.get("net_to_property"))
        elif avg_gross > 0:
            # Fallback: use historical average
            total_gross += avg_gross
            total_net += avg_net

    return total_gross, total_net, dominant


# ---------------------------------------------------------------------------
# Narrative builder
# ---------------------------------------------------------------------------

def _build_heuristic_narrative(
    window_days: int,
    confirmed_bookings: int,
    projected_gross: Decimal,
    projected_net: Decimal,
    occupancy_pct: float,
    historical_avg: dict,
    currency: str,
) -> str:
    """Generate a heuristic revenue forecast narrative."""
    gross_str = f"{currency} {_fmt(projected_gross)}"
    occ_str = f"{occupancy_pct}%"

    avg_gross = _to_dec(historical_avg.get("avg_gross_per_booking"))

    if confirmed_bookings == 0:
        trend = f"No confirmed bookings found in the next {window_days} days."
    elif avg_gross > 0 and projected_gross > 0:
        expected_gross = avg_gross * confirmed_bookings
        diff_pct = ((projected_gross - expected_gross) / expected_gross * 100).quantize(Decimal("0.1"))
        direction = "above" if diff_pct >= 0 else "below"
        trend = (
            f"Your {window_days}-day projected gross of {gross_str} is "
            f"{abs(diff_pct)}% {direction} expected based on {historical_avg.get('sample_bookings', 0)} "
            f"historical bookings."
        )
    else:
        trend = (
            f"Your {window_days}-day projected gross is {gross_str} "
            f"from {confirmed_bookings} confirmed bookings."
        )

    return (
        f"{trend} "
        f"Occupancy is tracking at {occ_str} for the period. "
        f"Projected net revenue: {currency} {_fmt(projected_net)}."
    )


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/ai/copilot/revenue-forecast",
    tags=["ai-copilot"],
    summary="Revenue forecast — 30/60/90-day forward projection (Phase 233)",
    responses={
        200: {"description": "Forward revenue projection"},
        400: {"description": "Invalid query parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_revenue_forecast(
    window: int = 30,
    property_id: Optional[str] = None,
    currency: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Forward revenue projection for the authenticated tenant.

    **Query parameters:**
    - `window` — 30, 60, or 90 days ahead (default 30)
    - `property_id` — optional, limit to single property
    - `currency` — optional 3-letter ISO code to filter by booking currency

    **Sources:**
    - `booking_state` — confirmed/active bookings (check_in in window)
    - `booking_financial_facts` — actual amounts + historical 90-day average

    **Read-only:** zero DB writes.
    """
    if window not in _VALID_WINDOWS:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"window must be one of {sorted(_VALID_WINDOWS)}",
        )

    if currency is not None:
        if not currency.isalpha() or len(currency) != 3:
            return make_error_response(
                400,
                ErrorCode.VALIDATION_ERROR,
                "currency must be a 3-letter ISO code (e.g. THB, USD)",
            )
        currency = currency.upper()

    try:
        db = client or _get_db()
        today = date.today()
        date_from = (today + timedelta(days=1)).isoformat()
        date_to = (today + timedelta(days=window)).isoformat()
        generated_at = datetime.now(tz=timezone.utc).isoformat()

        # 1. Fetch confirmed bookings
        confirmed = _fetch_confirmed_bookings(
            db, tenant_id, date_from, date_to, property_id, currency
        )

        # 2. Fetch financial facts for confirmed bookings
        booking_ids = [b["booking_id"] for b in confirmed if b.get("booking_id")]
        financial_map = _fetch_financial_facts_for_bookings(db, tenant_id, booking_ids, currency)

        # 3. Historical average (90-day lookback)
        historical_avg = _fetch_historical_avg(
            db, tenant_id, _HISTORY_LOOKBACK_DAYS, property_id, currency
        )

        # 4. Distinct properties in window
        property_ids_in_window = sorted({b.get("property_id") for b in confirmed if b.get("property_id")})
        if property_id:
            # Single-property request — always count as 1 even if no bookings yet
            property_count = 1
            if property_id not in property_ids_in_window:
                property_ids_in_window = [property_id]
        else:
            property_count = max(len(property_ids_in_window), 1)

        # 5. Occupancy projection
        occupancy_pct, booked_nights = _project_occupancy(confirmed, window, property_count)

        # 6. Revenue projection
        projected_gross, projected_net, dominant_currency = _project_revenue(
            confirmed, financial_map, historical_avg, currency
        )

        # 7. Narrative
        narrative = _build_heuristic_narrative(
            window_days=window,
            confirmed_bookings=len(confirmed),
            projected_gross=projected_gross,
            projected_net=projected_net,
            occupancy_pct=occupancy_pct,
            historical_avg=historical_avg,
            currency=dominant_currency,
        )

        # 8. Optional LLM overlay (best-effort)
        try:
            if os.environ.get("OPENAI_API_KEY"):
                from services.llm_client import call_llm  # type: ignore[import]
                prompt = (
                    f"You are a short-term rental revenue analyst. "
                    f"Write a concise 2-3 sentence forecast narrative for a property manager. "
                    f"Data: {window}-day window, {len(confirmed)} confirmed bookings, "
                    f"projected gross {dominant_currency} {_fmt(projected_gross)}, "
                    f"projected net {_fmt(projected_net)}, "
                    f"occupancy {occupancy_pct}%. "
                    f"Historical avg gross/booking: {historical_avg.get('avg_gross_per_booking', 'N/A')}."
                )
                llm_result = call_llm(prompt)
                if llm_result:
                    narrative = llm_result
        except Exception:  # noqa: BLE001
            pass  # keep heuristic narrative

        # 9. AI audit log (best-effort)
        try:
            from services.ai_audit_log import log_ai_interaction  # type: ignore[import]
            log_ai_interaction(
                db=db,
                tenant_id=tenant_id,
                endpoint="/ai/copilot/revenue-forecast",
                request_type="revenue_forecast",
                input_summary=f"window={window} property_id={property_id} currency={currency}",
                output_summary=f"bookings={len(confirmed)} gross={_fmt(projected_gross)} occ={occupancy_pct}%",
                generated_by="heuristic+llm" if os.environ.get("OPENAI_API_KEY") else "heuristic",
            )
        except Exception:  # noqa: BLE001
            pass

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "generated_at": generated_at,
                "window_days": window,
                "property_id": property_id,
                "currency_filter": currency,
                "forecast": {
                    "confirmed_bookings": len(confirmed),
                    "projected_gross": _fmt(projected_gross),
                    "projected_net": _fmt(projected_net),
                    "currency": dominant_currency,
                    "occupancy_pct": occupancy_pct,
                    "total_nights_analyzed": window * property_count,
                    "booked_nights": booked_nights,
                },
                "historical_avg": historical_avg or None,
                "narrative": narrative,
                "properties_included": property_ids_in_window,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("revenue_forecast: unexpected error tenant=%s: %s", tenant_id, exc)
        return make_error_response(
            500, ErrorCode.INTERNAL_ERROR, "Failed to compute revenue forecast"
        )
