"""
Phase 122 — OTA Financial Health Comparison (Ring 3)

GET /financial/ota-comparison?period=YYYY-MM

Compares per-OTA financial health metrics across all OTA providers active in the
requested period. Helps operators make smarter channel management decisions.

Metrics per OTA per currency:
  - booking_count          — unique bookings after dedup
  - gross_total            — sum of total_price
  - commission_total       — sum of ota_commission
  - net_total              — sum of net_to_property
  - avg_commission_rate    — mean(ota_commission / total_price × 100) per booking
  - net_to_gross_ratio     — mean(net_to_property / total_price) per booking
  - revenue_share_pct      — this OTA's gross / total-all-OTA gross × 100
  - epistemic_tier         — worst tier across all bookings for this OTA

Lifecycle distribution per OTA:
  - lifecycle_distribution — { "PAYOUT_RELEASED": 3, "RECONCILIATION_PENDING": 1, ... }

Rules:
  - JWT auth required.
  - Tenant isolation: .eq("tenant_id", tenant_id) enforced at DB level.
  - period param required — YYYY-MM format.
  - Reads from booking_financial_facts ONLY. Never reads booking_state.
  - Multi-currency: amounts never summed across currencies.
    Each (OTA, currency) bucket is independent.
  - Deduplication: most-recent recorded_at per booking_id (Phase 116 rule).
  - Bookings where total_price=0 or None excluded from ratio calculations
    (cannot divide by zero).
  - Revenue share pct computed from total gross across ALL OTAs, per currency.

Invariant (Phase 62+):
  This endpoint must NEVER read from or write to booking_state.

Invariant (Phase 116):
  All financial reads from booking_financial_facts ONLY.
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
from api.financial_aggregation_router import (
    _canonical_currency,
    _dedup_latest,
    _fetch_period_rows,
    _fmt,
    _to_decimal,
    _validate_period,
)
from api.financial_dashboard_router import (
    _tier,
    _worst_tier,
    _project_lifecycle_status,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client factory (patchable in tests)
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    """Return a Supabase client. Importable for test patching."""
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_ratio(numerator: Decimal, denominator: Decimal) -> Optional[Decimal]:
    """Return numerator / denominator or None if denominator is zero."""
    if denominator == Decimal("0"):
        return None
    return numerator / denominator


def _pct(ratio: Optional[Decimal]) -> Optional[str]:
    """Format an Optional ratio as a percentage string (×100, 2dp), or None."""
    if ratio is None:
        return None
    return _fmt(ratio * Decimal("100"))


def _build_ota_metrics(
    rows: List[dict],
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate per-(provider, currency) metrics from a list of deduped DB rows.

    Returns a nested dict:
      { provider: { currency: { ...metrics... } } }
    """
    # Accumulators: (provider, currency) → aggregator dict
    Agg = Dict[str, Any]
    agg: Dict[str, Dict[str, Agg]] = defaultdict(lambda: defaultdict(lambda: {
        "gross_vals": [],       # Decimal[]
        "commission_vals": [],  # Decimal[]
        "net_vals": [],         # Decimal[]
        "commission_rates": [], # Decimal[] (ota_commission / total_price)
        "net_to_gross": [],     # Decimal[] (net_to_property / total_price)
        "tiers": [],            # str[]
        "lifecycle": defaultdict(int),  # {status: count}
        "booking_ids": set(),   # for booking_count
    }))

    for row in rows:
        provider = row.get("provider") or "unknown"
        cur = _canonical_currency(row.get("currency"))
        event_kind = row.get("event_kind") or "BOOKING_CREATED"
        confidence = row.get("source_confidence") or "PARTIAL"

        gross = _to_decimal(row.get("total_price"))
        commission = _to_decimal(row.get("ota_commission"))
        net = _to_decimal(row.get("net_to_property"))

        bucket = agg[provider][cur]
        bucket["booking_ids"].add(row.get("booking_id", ""))
        bucket["tiers"].append(_tier(confidence))
        bucket["gross_vals"].append(gross)
        bucket["commission_vals"].append(commission)
        bucket["net_vals"].append(net)

        # Ratios — only when gross > 0
        if gross > Decimal("0"):
            comm_rate = _safe_ratio(commission, gross)
            ntg = _safe_ratio(net, gross)
            if comm_rate is not None:
                bucket["commission_rates"].append(comm_rate)
            if ntg is not None:
                bucket["net_to_gross"].append(ntg)

        # Lifecycle
        lifecycle_status = _project_lifecycle_status(row, event_kind)
        bucket["lifecycle"][lifecycle_status] += 1

    return agg  # type: ignore[return-value]


def _compute_revenue_share(
    agg: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Optional[Decimal]]]:
    """
    Compute revenue share pct per (provider, currency).

    For each currency, sum gross_total across ALL providers, then compute
    each provider's share as (provider_gross / total_gross × 100).
    """
    # Sum gross by currency across all providers
    total_gross_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for cur_map in agg.values():
        for cur, bucket in cur_map.items():
            total_gross_by_cur[cur] += sum(bucket["gross_vals"], Decimal("0"))

    # Build shares
    shares: Dict[str, Dict[str, Optional[Decimal]]] = {}
    for provider, cur_map in agg.items():
        shares[provider] = {}
        for cur, bucket in cur_map.items():
            provider_gross = sum(bucket["gross_vals"], Decimal("0"))
            total = total_gross_by_cur[cur]
            shares[provider][cur] = _safe_ratio(provider_gross, total)

    return shares


def _avg(vals: List[Decimal]) -> Optional[Decimal]:
    """Mean of a list, or None if empty."""
    if not vals:
        return None
    return sum(vals, Decimal("0")) / Decimal(str(len(vals)))


# ---------------------------------------------------------------------------
# GET /financial/ota-comparison
# ---------------------------------------------------------------------------

@router.get(
    "/financial/ota-comparison",
    tags=["financial-dashboard"],
    summary="OTA financial health comparison for the period",
    responses={
        200: {"description": "Per-OTA financial health metrics grouped by currency"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_ota_comparison(
    period: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Compare financial health metrics across all OTA providers for the period.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    Per-OTA, per-currency breakdown of:
    - `booking_count` — unique bookings after dedup
    - `gross_total`, `commission_total`, `net_total` — monetary totals (strings, 2dp)
    - `avg_commission_rate` — mean commission% per booking (or null if no gross data)
    - `net_to_gross_ratio` — mean net/gross ratio per booking (or null if no gross data)
    - `revenue_share_pct` — this OTA's gross as % of all-OTA gross (per currency)
    - `epistemic_tier` — worst tier (A/B/C) across all bookings for this OTA
    - `lifecycle_distribution` — count per PaymentLifecycleStatus

    **Deduplication:** Most-recent `recorded_at` per `booking_id` (per Phase 116).

    **Multi-currency:** No cross-currency arithmetic. Each currency is independent.

    **Source:** Reads from `booking_financial_facts` only.
    Never reads `booking_state`.
    """
    err = _validate_period(period)
    if err:
        return err

    try:
        db = client if client is not None else _get_supabase_client()
        rows = _fetch_period_rows(db, tenant_id, period)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        if not deduped:
            return JSONResponse(
                status_code=200,
                content={
                    "tenant_id": tenant_id,
                    "period": period,
                    "total_bookings": 0,
                    "providers": {},
                },
            )

        agg = _build_ota_metrics(deduped)
        shares = _compute_revenue_share(agg)

        providers_out: Dict[str, Any] = {}
        for provider in sorted(agg.keys()):
            cur_map = agg[provider]
            providers_out[provider] = {}
            for cur in sorted(cur_map.keys()):
                bucket = cur_map[cur]

                gross_total = sum(bucket["gross_vals"], Decimal("0"))
                commission_total = sum(bucket["commission_vals"], Decimal("0"))
                net_total = sum(bucket["net_vals"], Decimal("0"))

                avg_comm_rate = _avg(bucket["commission_rates"])
                avg_ntg = _avg(bucket["net_to_gross"])
                rev_share = shares[provider][cur]
                worst = _worst_tier(bucket["tiers"])

                providers_out[provider][cur] = {
                    "booking_count": len(bucket["booking_ids"]),
                    "gross_total": _fmt(gross_total),
                    "commission_total": _fmt(commission_total),
                    "net_total": _fmt(net_total),
                    "avg_commission_rate": _pct(avg_comm_rate),
                    "net_to_gross_ratio": _pct(avg_ntg),
                    "revenue_share_pct": _pct(rev_share),
                    "epistemic_tier": worst,
                    "lifecycle_distribution": dict(sorted(bucket["lifecycle"].items())),
                }

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "period": period,
                "total_bookings": len(deduped),
                "providers": providers_out,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /financial/ota-comparison error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
