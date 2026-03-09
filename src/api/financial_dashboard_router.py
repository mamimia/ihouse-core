"""
Phase 118 — Financial Dashboard API (Ring 2–3)

Extends Phase 116 (Financial Aggregation API) with three new read-only endpoints:

    GET /financial/status/{booking_id}
        Per-booking financial status card.
        Returns lifecycle_status, monetary fields, source_confidence,
        epistemic_tier, and a plain-English reason from explain_payment_lifecycle().

    GET /financial/revpar?property_id=&period=YYYY-MM
        RevPAR (Revenue Per Available Room Night) computation.
        total_revenue / available_room_nights, per currency.
        Returns an epistemic_tier based on worst source_confidence in the period.

    GET /financial/lifecycle-by-property?period=YYYY-MM
        Lifecycle distribution grouped by property, per currency.
        Same dedup rules as Phase 116 (most-recent recorded_at per booking_id).

Invariants:
    - Reads from booking_financial_facts ONLY. Never booking_state.
    - All monetary fields returned as strings (Decimal precision preserved).
    - Epistemic tier computed from source_confidence:
        FULL      → "A"  (measured — direct from OTA)
        ESTIMATED → "B"  (derived — calculated from other fields)
        PARTIAL   → "C"  (incomplete — some fields missing)
    - JWT auth required on all endpoints.
    - Tenant isolation enforced via .eq("tenant_id", tenant_id).

Epistemic tier rule for aggregated endpoints:
    The tier of a result is the WORST (most uncertain) tier in the input.
    A=best, C=worst. Mixed: any C → C, no C but any B → B, all A → A.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from api.financial_aggregation_router import (
    SUPPORTED_CURRENCIES,
    _canonical_currency,
    _dedup_latest,
    _fetch_period_rows,
    _fmt,
    _get_supabase_client,
    _month_bounds,
    _to_decimal,
    _validate_period,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Epistemic tier helpers
# ---------------------------------------------------------------------------

_CONFIDENCE_TIER: Dict[str, str] = {
    "FULL": "A",
    "ESTIMATED": "B",
    "PARTIAL": "C",
}
_TIER_ORDER: Dict[str, int] = {"A": 0, "B": 1, "C": 2}  # higher = worse


def _tier(confidence: Optional[str]) -> str:
    """Return epistemic tier for a single confidence value."""
    return _CONFIDENCE_TIER.get((confidence or "").upper(), "C")


def _worst_tier(tiers: List[str]) -> str:
    """Return the worst (most uncertain) tier from a list."""
    if not tiers:
        return "C"
    return max(tiers, key=lambda t: _TIER_ORDER.get(t, 2))


def _monetary(v: Optional[str]) -> Optional[str]:
    """Format a nullable monetary string to 2dp, or keep None."""
    if v is None:
        return None
    try:
        return _fmt(Decimal(str(v)))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# GET /financial/status/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/financial/status/{booking_id}",
    tags=["financial"],
    summary="Per-booking financial status card with lifecycle projection",
    responses={
        200: {"description": "Booking financial status card"},
        404: {"description": "No financial record found for this booking"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_financial_status(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return a financial status card for a single booking.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Path parameters:**
    - `booking_id` — the booking identifier (e.g. `bookingcom_RES123456`)

    **Returns:**
    - `lifecycle_status` — projected PaymentLifecycleStatus
    - `epistemic_tier` — A (FULL) / B (ESTIMATED) / C (PARTIAL)
    - `total_price`, `ota_commission`, `net_to_property` — strings or null
    - `currency`, `source_confidence`, `provider`, `event_kind`
    - `reason` — plain-English explanation from explain_payment_lifecycle()

    **Source:** Reads from `booking_financial_facts` only.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []

        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"detail": f"No financial record found for booking_id={booking_id!r}"},
            )

        row = rows[0]
        confidence = row.get("source_confidence") or "PARTIAL"
        event_kind = row.get("event_kind") or "BOOKING_CREATED"
        tier = _tier(confidence)

        # Build financial facts for lifecycle projection
        reason_text: str = _build_lifecycle_reason(row, event_kind)
        lifecycle_status: str = _project_lifecycle_status(row, event_kind)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "booking_id": booking_id,
                "lifecycle_status": lifecycle_status,
                "epistemic_tier": tier,
                "total_price": _monetary(row.get("total_price")),
                "ota_commission": _monetary(row.get("ota_commission")),
                "net_to_property": _monetary(row.get("net_to_property")),
                "currency": row.get("currency"),
                "source_confidence": confidence,
                "provider": row.get("provider"),
                "event_kind": event_kind,
                "reason": reason_text,
                "recorded_at": row.get("recorded_at"),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /financial/status/%s error for tenant=%s: %s", booking_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


def _project_lifecycle_status(row: dict, event_kind: str) -> str:
    """Project PaymentLifecycleStatus from a booking_financial_facts row."""
    try:
        from adapters.ota.payment_lifecycle import project_payment_lifecycle
        from adapters.ota.financial_extractor import BookingFinancialFacts

        total_price = _to_decimal(row.get("total_price")) or None
        if total_price == Decimal("0"):
            total_price = None

        net_to_property = _to_decimal(row.get("net_to_property")) or None
        if net_to_property == Decimal("0"):
            net_to_property = None

        ota_commission = _to_decimal(row.get("ota_commission")) or None
        if ota_commission == Decimal("0"):
            ota_commission = None

        facts = BookingFinancialFacts(
            total_price=total_price,
            net_to_property=net_to_property,
            ota_commission=ota_commission,
            currency=row.get("currency"),
            source_confidence=row.get("source_confidence") or "PARTIAL",
            provider=row.get("provider") or "unknown",
        )
        canonical = _normalize_event_kind(event_kind)
        return project_payment_lifecycle(facts, canonical).value
    except Exception:
        return "UNKNOWN"


def _build_lifecycle_reason(row: dict, event_kind: str) -> str:
    """Return plain-English reason from explain_payment_lifecycle."""
    try:
        from adapters.ota.payment_lifecycle import explain_payment_lifecycle
        from adapters.ota.financial_extractor import BookingFinancialFacts

        total_price = _to_decimal(row.get("total_price")) or None
        if total_price == Decimal("0"):
            total_price = None

        net_to_property = _to_decimal(row.get("net_to_property")) or None
        if net_to_property == Decimal("0"):
            net_to_property = None

        ota_commission = _to_decimal(row.get("ota_commission")) or None
        if ota_commission == Decimal("0"):
            ota_commission = None

        facts = BookingFinancialFacts(
            total_price=total_price,
            net_to_property=net_to_property,
            ota_commission=ota_commission,
            currency=row.get("currency"),
            source_confidence=row.get("source_confidence") or "PARTIAL",
            provider=row.get("provider") or "unknown",
        )
        canonical = _normalize_event_kind(event_kind)
        explanation = explain_payment_lifecycle(facts, canonical)
        return explanation.reason
    except Exception:
        return "Lifecycle explanation unavailable."


def _normalize_event_kind(event_kind: str) -> str:
    """Map event_kind from booking_financial_facts to a canonical envelope type."""
    mapping = {
        "BOOKING_CREATED": "BOOKING_CREATED",
        "BOOKING_AMENDED": "BOOKING_AMENDED",
        "BOOKING_CANCELED": "BOOKING_CANCELED",
        "BOOKING_CANCELLED": "BOOKING_CANCELED",  # handle both spellings
    }
    return mapping.get((event_kind or "").upper(), "BOOKING_CREATED")


# ---------------------------------------------------------------------------
# GET /financial/revpar
# ---------------------------------------------------------------------------

@router.get(
    "/financial/revpar",
    tags=["financial"],
    summary="RevPAR (Revenue Per Available Room Night) for a property and period",
    responses={
        200: {"description": "RevPAR computation with epistemic tier"},
        400: {"description": "Missing or invalid period or property_id parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_revpar(
    period: Optional[str] = None,
    property_id: Optional[str] = None,
    available_room_nights: Optional[int] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Compute RevPAR (Revenue Per Available Room Night) for a property.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format
    - `property_id` *(required)* — property to compute RevPAR for
    - `available_room_nights` *(optional)* — denominator for RevPAR computation.
      If omitted, total_revenue is returned without division (useful for
      properties reporting aggregate revenue).

    **Formula:** `RevPAR = total_net_revenue / available_room_nights`

    **Returns:**
    - `revpar` per currency (or `total_net` if available_room_nights not provided)
    - `epistemic_tier` — worst tier across all bookings in the period
    - `total_bookings` — number of unique bookings after dedup

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err

    if not property_id:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "property_id query parameter is required"},
        )

    try:
        db = client if client is not None else _get_supabase_client()
        month_start, month_end = _month_bounds(period)  # type: ignore[arg-type]

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .gte("recorded_at", month_start)
            .lt("recorded_at", month_end)
            .order("recorded_at", desc=False)
            .execute()
        )
        rows = result.data or []
        deduped = _dedup_latest(rows)

        # Aggregate per currency
        net_by_cur: Dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        tiers_by_cur: Dict[str, List[str]] = defaultdict(list)

        for row in deduped:
            cur = _canonical_currency(row.get("currency"))
            net_by_cur[cur] += _to_decimal(row.get("net_to_property"))
            tiers_by_cur[cur].append(_tier(row.get("source_confidence")))

        currencies_out: Dict[str, Any] = {}
        for cur in sorted(net_by_cur.keys()):
            total_net = net_by_cur[cur]
            worst = _worst_tier(tiers_by_cur[cur])
            if available_room_nights and available_room_nights > 0:
                revpar_val = _fmt(total_net / Decimal(str(available_room_nights)))
                currencies_out[cur] = {
                    "revpar": revpar_val,
                    "total_net": _fmt(total_net),
                    "available_room_nights": available_room_nights,
                    "epistemic_tier": worst,
                }
            else:
                currencies_out[cur] = {
                    "revpar": None,
                    "total_net": _fmt(total_net),
                    "available_room_nights": None,
                    "epistemic_tier": worst,
                }

        overall_tier = _worst_tier([v["epistemic_tier"] for v in currencies_out.values()]) if currencies_out else "C"

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "property_id": property_id,
                "period": period,
                "total_bookings": len(deduped),
                "overall_epistemic_tier": overall_tier,
                "currencies": currencies_out,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /financial/revpar error for tenant=%s property=%s: %s",
            tenant_id, property_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /financial/lifecycle-by-property
# ---------------------------------------------------------------------------

@router.get(
    "/financial/lifecycle-by-property",
    tags=["financial"],
    summary="Lifecycle distribution grouped by property for the period",
    responses={
        200: {"description": "Per-property lifecycle distribution"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_lifecycle_by_property(
    period: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Lifecycle distribution grouped by property for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    Per-property dict mapping property_id → lifecycle status → count.
    Properties missing property_id appear under `"unknown"`.

    **Deduplication:** Most-recent recorded_at per booking_id (same as Phase 116).

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err

    try:
        db = client if client is not None else _get_supabase_client()
        rows = _fetch_period_rows(db, tenant_id, period)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        # distribution[prop_id][lifecycle_status] = count
        distribution: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for row in deduped:
            prop = row.get("property_id") or "unknown"
            event_kind = row.get("event_kind") or "BOOKING_CREATED"
            status = _project_lifecycle_status(row, event_kind)
            distribution[prop][status] += 1

        dist_out = {
            prop: dict(sorted(counts.items()))
            for prop, counts in sorted(distribution.items())
        }

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "period": period,
                "total_bookings": len(deduped),
                "properties": dist_out,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /financial/lifecycle-by-property error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
