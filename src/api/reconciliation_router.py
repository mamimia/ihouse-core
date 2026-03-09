"""
Phase 119 — Reconciliation Inbox API

GET /admin/reconciliation?period=YYYY-MM

Exception-first view of bookings that need operator attention.
Returns only bookings that match at least one exception criterion.
An empty inbox means clean financials — nothing to act on.

Exception criteria (any one triggers inclusion):
    1. lifecycle_status == RECONCILIATION_PENDING
    2. source_confidence == PARTIAL
    3. net_to_property is NULL or missing
    4. lifecycle_status == UNKNOWN

Response per item:
    - booking_id, provider, property_id, currency
    - lifecycle_status, source_confidence, epistemic_tier (A/B/C)
    - total_price, ota_commission, net_to_property (strings or null)
    - flags: list of exception reasons fired for this booking
    - correction_hint: human-readable hint where inferable, else null

Invariants:
    - Reads from booking_financial_facts ONLY. Never booking_state.
    - JWT auth required.
    - Tenant isolation via .eq("tenant_id", tenant_id).
    - Deduplication: most-recent recorded_at per booking_id (same rule as Phase 116).
    - period param required, YYYY-MM format.
    - Items sorted by epistemic_tier (C first) then by booking_id.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from api.financial_aggregation_router import (
    _dedup_latest,
    _fetch_period_rows,
    _get_supabase_client,
    _validate_period,
)
from api.financial_dashboard_router import (
    _monetary,
    _project_lifecycle_status,
    _tier,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Exception flags
# ---------------------------------------------------------------------------

FLAG_RECONCILIATION_PENDING = "RECONCILIATION_PENDING"
FLAG_PARTIAL_CONFIDENCE = "PARTIAL_CONFIDENCE"
FLAG_MISSING_NET = "MISSING_NET_TO_PROPERTY"
FLAG_UNKNOWN_LIFECYCLE = "UNKNOWN_LIFECYCLE"

_TIER_SORT_ORDER = {"C": 0, "B": 1, "A": 2}  # C first (worst/most urgent)


# ---------------------------------------------------------------------------
# Correction hint builder
# ---------------------------------------------------------------------------

def _correction_hint(flags: List[str], row: dict) -> Optional[str]:
    """
    Return a human-readable correction hint where inferable, else None.

    Hints are short, operator-friendly, and actionable.
    """
    if FLAG_RECONCILIATION_PENDING in flags:
        event_kind = row.get("event_kind") or ""
        if "CANCELED" in event_kind.upper():
            return (
                "Booking was canceled. Verify refund issued and payout reversal "
                "confirmed with the OTA."
            )
        return (
            "Financial discrepancy detected. Cross-check OTA statement "
            "against recorded amounts."
        )

    if FLAG_MISSING_NET in flags and FLAG_PARTIAL_CONFIDENCE in flags:
        total = row.get("total_price")
        provider = row.get("provider") or "OTA"
        if total:
            return (
                f"net_to_property is missing. Estimated net ≈ {total} "
                f"minus {provider} commission rate. Check {provider} payout settings."
            )
        return (
            "Both net_to_property and total_price are unavailable. "
            "Manual lookup required from OTA dashboard."
        )

    if FLAG_MISSING_NET in flags:
        return (
            "net_to_property is missing from this record. "
            "May resolve automatically on next webhook sync."
        )

    if FLAG_UNKNOWN_LIFECYCLE in flags:
        return (
            "Insufficient financial data to project payment state. "
            "Check OTA webhook for this booking_id."
        )

    return None


# ---------------------------------------------------------------------------
# Row → exception item
# ---------------------------------------------------------------------------

def _build_exception_item(row: dict) -> Optional[Dict[str, Any]]:
    """
    Evaluate a single (deduped) booking row against exception criteria.
    Returns a dict if at least one flag fires, else None.
    """
    event_kind = row.get("event_kind") or "BOOKING_CREATED"
    lifecycle_status = _project_lifecycle_status(row, event_kind)
    confidence = row.get("source_confidence") or "PARTIAL"
    net = row.get("net_to_property")
    tier = _tier(confidence)

    flags: List[str] = []

    if lifecycle_status == "RECONCILIATION_PENDING":
        flags.append(FLAG_RECONCILIATION_PENDING)

    if confidence.upper() == "PARTIAL":
        flags.append(FLAG_PARTIAL_CONFIDENCE)

    if net is None:
        flags.append(FLAG_MISSING_NET)

    if lifecycle_status == "UNKNOWN":
        flags.append(FLAG_UNKNOWN_LIFECYCLE)

    if not flags:
        return None  # clean — not included

    hint = _correction_hint(flags, row)

    return {
        "booking_id": row.get("booking_id"),
        "provider": row.get("provider"),
        "property_id": row.get("property_id"),
        "currency": row.get("currency"),
        "event_kind": event_kind,
        "lifecycle_status": lifecycle_status,
        "source_confidence": confidence,
        "epistemic_tier": tier,
        "total_price": _monetary(row.get("total_price")),
        "ota_commission": _monetary(row.get("ota_commission")),
        "net_to_property": _monetary(net),
        "flags": flags,
        "correction_hint": hint,
        "recorded_at": row.get("recorded_at"),
    }


# ---------------------------------------------------------------------------
# GET /admin/reconciliation
# ---------------------------------------------------------------------------

@router.get(
    "/admin/reconciliation",
    tags=["admin"],
    summary="Reconciliation inbox — bookings requiring operator attention",
    responses={
        200: {"description": "List of exception bookings, sorted by urgency"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_reconciliation_inbox(
    period: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Exception-first reconciliation inbox for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    A list of bookings that match at least one exception criterion:
    - `RECONCILIATION_PENDING` lifecycle status
    - `PARTIAL` source confidence
    - Missing `net_to_property`
    - `UNKNOWN` lifecycle status

    Each item includes `flags` (list of exception reasons) and a
    `correction_hint` (human-readable guidance) where inferable.

    **Empty inbox:** An empty `items` list means no exceptions — financials
    are clean for this period.

    **Sort order:** Tier C (most uncertain) first, then by booking_id.

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err

    try:
        db = client if client is not None else _get_supabase_client()
        rows = _fetch_period_rows(db, tenant_id, period)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        items: List[Dict[str, Any]] = []
        for row in deduped:
            item = _build_exception_item(row)
            if item is not None:
                items.append(item)

        # Sort: C tier first (most urgent), then booking_id alphabetically
        items.sort(
            key=lambda x: (
                _TIER_SORT_ORDER.get(x["epistemic_tier"], 99),
                x["booking_id"] or "",
            )
        )

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "period": period,
                "total_bookings_checked": len(deduped),
                "exception_count": len(items),
                "items": items,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/reconciliation error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
