"""
Phase 244 — OTA Revenue Mix Analytics API

GET /admin/ota/revenue-mix

All-time view of how each OTA channel contributes to total revenue across
the entire tenant portfolio. Complements Phase 122's period-scoped comparison
with a broader, time-unrestricted perspective.

Metrics per OTA per currency:
  - booking_count       — unique bookings after dedup (latest recorded_at per booking_id)
  - gross_total         — sum of total_price
  - commission_total    — sum of ota_commission
  - net_total           — sum of net_to_property
  - avg_commission_rate — mean OTA commission % across bookings (or null)
  - net_to_gross_ratio  — mean net/gross ratio per booking (or null)
  - revenue_share_pct   — this OTA's gross / all-OTAs gross × 100 (per currency)

Portfolio-level summary:
  - total_bookings
  - total_gross_by_currency
  - total_net_by_currency
  - provider_count

Architecture invariants:
    - Reads booking_financial_facts ONLY. Never reads booking_state.
    - Multi-currency: amounts never summed across currencies.
    - Deduplication: latest recorded_at per booking_id.
    - JWT auth required.
    - Tenant isolation via .eq("tenant_id", tenant_id).
    - No period param — all-time snapshot.

Response shape:
    {
        "tenant_id": "...",
        "generated_at": "...",
        "total_bookings": 120,
        "provider_count": 3,
        "portfolio_totals": {
            "gross_by_currency": { "THB": "152340.00" },
            "net_by_currency": { "THB": "130000.00" }
        },
        "providers": {
            "airbnb": {
                "THB": {
                    "booking_count": 55,
                    "gross_total": "80000.00",
                    "commission_total": "12000.00",
                    "net_total": "68000.00",
                    "avg_commission_rate": "15.00",
                    "net_to_gross_ratio": "85.00",
                    "revenue_share_pct": "52.51"
                }
            }
        }
    }
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
# Monetary helpers (standalone, no import from other routers)
# ---------------------------------------------------------------------------

def _to_dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _fmt(v: Decimal) -> str:
    return f"{v:.2f}"


def _safe_pct(numerator: Decimal, denominator: Decimal) -> Optional[str]:
    """Return numerator/denominator × 100 as a 2dp string, or None."""
    if denominator == Decimal("0"):
        return None
    return _fmt(numerator / denominator * Decimal("100"))


def _avg_pct(ratios: List[Decimal]) -> Optional[str]:
    """Mean of a list of ratios (already 0–1 scale) × 100, or None."""
    if not ratios:
        return None
    mean = sum(ratios, Decimal("0")) / Decimal(str(len(ratios)))
    return _fmt(mean * Decimal("100"))


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _dedup_latest(rows: List[dict]) -> List[dict]:
    """Keep only the most-recent recorded_at row per booking_id."""
    seen: set = set()
    result = []
    for row in rows:
        bid = row.get("booking_id")
        if bid and bid not in seen:
            seen.add(bid)
            result.append(row)
    return result


# ---------------------------------------------------------------------------
# Canonical currency
# ---------------------------------------------------------------------------

def _canonical_currency(c: Optional[str]) -> str:
    return (c or "UNKNOWN").upper().strip()


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate(rows: List[dict]) -> Dict[str, Dict[str, Any]]:
    """
    Build per-(provider, currency) buckets from deduplicated rows.

    Returns:
        { provider: { currency: { gross_vals, commission_vals, net_vals,
                                  commission_rates, net_to_gross, booking_ids } } }
    """
    agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: defaultdict(lambda: {
            "gross_vals": [],
            "commission_vals": [],
            "net_vals": [],
            "commission_rates": [],  # ratio 0-1
            "net_to_gross": [],      # ratio 0-1
            "booking_ids": set(),
        })
    )

    for row in rows:
        provider = row.get("provider") or "unknown"
        cur = _canonical_currency(row.get("currency"))
        gross = _to_dec(row.get("total_price"))
        commission = _to_dec(row.get("ota_commission"))
        net = _to_dec(row.get("net_to_property"))

        bucket = agg[provider][cur]
        bucket["booking_ids"].add(row.get("booking_id", ""))
        bucket["gross_vals"].append(gross)
        bucket["commission_vals"].append(commission)
        bucket["net_vals"].append(net)

        if gross > Decimal("0"):
            bucket["commission_rates"].append(commission / gross)
            bucket["net_to_gross"].append(net / gross)

    return agg


def _revenue_shares(
    agg: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Optional[str]]]:
    """Compute each provider's gross share of the all-provider gross, per currency."""
    total_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for cur_map in agg.values():
        for cur, bucket in cur_map.items():
            total_by_cur[cur] += sum(bucket["gross_vals"], Decimal("0"))

    shares: Dict[str, Dict[str, Optional[str]]] = {}
    for provider, cur_map in agg.items():
        shares[provider] = {}
        for cur, bucket in cur_map.items():
            provider_gross = sum(bucket["gross_vals"], Decimal("0"))
            shares[provider][cur] = _safe_pct(provider_gross, total_by_cur[cur])

    return shares


def _portfolio_totals(agg: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate gross and net totals across all providers, per currency."""
    gross_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    net_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

    for cur_map in agg.values():
        for cur, bucket in cur_map.items():
            gross_by_cur[cur] += sum(bucket["gross_vals"], Decimal("0"))
            net_by_cur[cur] += sum(bucket["net_vals"], Decimal("0"))

    currencies = sorted(set(gross_by_cur) | set(net_by_cur))
    return {
        "gross_by_currency": {c: _fmt(gross_by_cur[c]) for c in currencies},
        "net_by_currency": {c: _fmt(net_by_cur[c]) for c in currencies},
    }


# ---------------------------------------------------------------------------
# GET /admin/ota/revenue-mix
# ---------------------------------------------------------------------------

@router.get(
    "/admin/ota/revenue-mix",
    tags=["admin"],
    summary="All-time OTA revenue mix: gross, net, commission and share per channel",
    responses={
        200: {"description": "Per-OTA revenue breakdown with portfolio totals"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_ota_revenue_mix(
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    All-time OTA revenue mix for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **No query parameters** — all-time snapshot, not period-filtered.

    **Returns:**
    - `provider_count` — number of distinct OTA providers
    - `total_bookings` — total unique bookings (all providers combined)
    - `portfolio_totals` — aggregate gross/net revenue by currency
    - `providers` — per-OTA, per-currency breakdown:
        - `booking_count`, `gross_total`, `commission_total`, `net_total`
        - `avg_commission_rate` — mean commission% (as string, null if no gross data)
        - `net_to_gross_ratio` — mean net/gross ratio% (as string, null if no gross data)
        - `revenue_share_pct` — this OTA's gross share of all-OTA gross (per currency)

    **Source:** `booking_financial_facts` only. Never reads `booking_state`.
    **Deduplication:** latest `recorded_at` per `booking_id`.
    """
    from datetime import datetime, timezone

    generated_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        # Read all financial facts for this tenant (all-time)
        result = (
            db.table("booking_financial_facts")
            .select(
                "booking_id, provider, currency, total_price, ota_commission, "
                "net_to_property, recorded_at"
            )
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
            .execute()
        )
        rows = result.data or []
        deduped = _dedup_latest(rows)

        if not deduped:
            return JSONResponse(
                status_code=200,
                content={
                    "tenant_id": tenant_id,
                    "generated_at": generated_at,
                    "total_bookings": 0,
                    "provider_count": 0,
                    "portfolio_totals": {"gross_by_currency": {}, "net_by_currency": {}},
                    "providers": {},
                },
            )

        agg = _aggregate(deduped)
        shares = _revenue_shares(agg)
        totals = _portfolio_totals(agg)

        # Build output
        providers_out: Dict[str, Any] = {}
        for provider in sorted(agg.keys()):
            cur_map = agg[provider]
            providers_out[provider] = {}
            for cur in sorted(cur_map.keys()):
                bucket = cur_map[cur]
                gross_total = sum(bucket["gross_vals"], Decimal("0"))
                commission_total = sum(bucket["commission_vals"], Decimal("0"))
                net_total = sum(bucket["net_vals"], Decimal("0"))

                providers_out[provider][cur] = {
                    "booking_count": len(bucket["booking_ids"]),
                    "gross_total": _fmt(gross_total),
                    "commission_total": _fmt(commission_total),
                    "net_total": _fmt(net_total),
                    "avg_commission_rate": _avg_pct(bucket["commission_rates"]),
                    "net_to_gross_ratio": _avg_pct(bucket["net_to_gross"]),
                    "revenue_share_pct": shares[provider][cur],
                }

        # Total bookings = unique booking_ids across all providers/currencies
        all_booking_ids: set = set()
        for cur_map in agg.values():
            for bucket in cur_map.values():
                all_booking_ids |= bucket["booking_ids"]

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "generated_at": generated_at,
                "total_bookings": len(all_booking_ids),
                "provider_count": len(providers_out),
                "portfolio_totals": totals,
                "providers": providers_out,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/ota/revenue-mix error for tenant=%s: %s",
            tenant_id,
            exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
