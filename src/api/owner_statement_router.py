"""
Phase 121 — Owner Statement Generator (Ring 4)

GET /owner-statement/{property_id}?month=YYYY-MM[&management_fee_pct=X.X][&format=pdf]

Enhanced owner statement: per-booking line items with check-in / check-out dates,
OTA provider, gross amount, OTA commission, net-to-property, payout lifecycle status,
and epistemic tier (A/B/C) on every monetary figure.

Management fee:
    Optional `management_fee_pct` query param (0.0–100.0).
    Applied on the owner_net = net_to_property - (net_to_property * fee_pct / 100).
    Management fee deduction appears as a separate line in the summary.

PDF export:
    `?format=pdf` returns Content-Type: text/plain with a human-readable statement body.
    No external PDF library — plain text is the Phase 121 contract.

Role-scoping:
    property_id filter is enforced at DB level using the `property_id` column in
    booking_financial_facts. Only records where property_id = the requested value
    are returned (tenant isolation already enforced via tenant_id).

Epistemic tier:
    FULL      → "A"  (direct from OTA — measured)
    ESTIMATED → "B"  (derived — calculated from other OTA fields)
    PARTIAL   → "C"  (incomplete — some fields missing)
    Worst tier wins in the statement summary.

Rules:
- JWT auth required.
- Tenant isolation: only records for this tenant are returned.
- `month` query parameter required — format YYYY-MM.
- `property_id` filter applied at DB level (property_id column).
- Returns 404 if no financial records found for this property + month + tenant.
- Reads from booking_financial_facts only. Never reads booking_state.
- Deduplication: most-recent recorded_at per booking_id.
- OTA_COLLECTING bookings are visible in line items but marked explicitly.

Invariant (locked Phase 62+):
  This endpoint must NEVER read from or write to booking_state.

Invariant (Phase 116):
  All financial reads from booking_financial_facts ONLY.

Invariant (Phase 120):
  OTA_COLLECTING NEVER counted as received payout.
"""
from __future__ import annotations

import logging
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from api.financial_aggregation_router import (
    _dedup_latest,
    _fmt,
    _month_bounds,
    _to_decimal,
    _canonical_currency,
)
from api.financial_dashboard_router import (
    _tier,
    _worst_tier,
    _project_lifecycle_status,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_MAX_MGMT_FEE = Decimal("100")
_MIN_MGMT_FEE = Decimal("0")


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_mgmt_fee(raw: Optional[str]) -> Optional[Decimal]:
    """
    Parse and validate management_fee_pct.
    Returns None on bad input (will cause a 400 upstream).
    Returns Decimal('0') if raw is None (fee not requested).
    """
    if raw is None:
        return Decimal("0")
    try:
        val = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if val < _MIN_MGMT_FEE or val > _MAX_MGMT_FEE:
        return None
    return val


def _optional_str(val: Optional[Decimal]) -> Optional[str]:
    """Decimal → 2dp string, or None."""
    if val is None:
        return None
    return _fmt(val)


def _build_line_item(row: dict) -> Dict[str, Any]:
    """
    Build one statement line item from a booking_financial_facts DB row.
    Returns a dict ready for JSON serialization.
    """
    event_kind = row.get("event_kind") or "BOOKING_CREATED"
    confidence = row.get("source_confidence") or "PARTIAL"
    tier = _tier(confidence)
    lifecycle = _project_lifecycle_status(row, event_kind)

    total_price = _to_decimal(row.get("total_price")) or None
    if total_price == Decimal("0"):
        total_price = None

    ota_commission = _to_decimal(row.get("ota_commission")) or None
    if ota_commission == Decimal("0"):
        ota_commission = None

    net_to_property = _to_decimal(row.get("net_to_property")) or None
    if net_to_property == Decimal("0"):
        net_to_property = None

    # Extract check-in / check-out from raw_financial_fields if present,
    # or from the row directly (some adapters store canonical keys).
    raw_fields = row.get("raw_financial_fields") or {}
    check_in = (
        row.get("check_in")
        or raw_fields.get("canonical_check_in")
        or raw_fields.get("check_in")
        or raw_fields.get("canonical_check_in_date")
    )
    check_out = (
        row.get("check_out")
        or raw_fields.get("canonical_check_out")
        or raw_fields.get("check_out")
        or raw_fields.get("canonical_check_out_date")
    )

    return {
        "booking_id": row.get("booking_id", "unknown"),
        "provider": row.get("provider") or "unknown",
        "currency": row.get("currency"),
        "check_in": check_in,
        "check_out": check_out,
        "gross": _optional_str(total_price),
        "ota_commission": _optional_str(ota_commission),
        "net_to_property": _optional_str(net_to_property),
        "source_confidence": confidence,
        "epistemic_tier": tier,
        "lifecycle_status": lifecycle,
        "event_kind": event_kind,
        "recorded_at": row.get("recorded_at"),
    }


def _compute_summary(
    line_items: List[Dict[str, Any]],
    mgmt_fee_pct: Decimal,
) -> Dict[str, Any]:
    """
    Aggregate line items into a statement summary.

    Rules:
    - Exclude OTA_COLLECTING from owner_net calculation (honest — not yet received).
    - Worst epistemic tier wins.
    - Multi-currency: if currencies differ, monetary totals are None.
    - Management fee applied to the aggregated net_to_property.
    """
    currencies = {item["currency"] for item in line_items if item["currency"]}
    is_multi_currency = len(currencies) > 1
    currency = "MIXED" if is_multi_currency else (next(iter(currencies), "UNKNOWN"))

    # Collect figures for single-currency path
    gross_vals: List[Decimal] = []
    commission_vals: List[Decimal] = []
    net_vals: List[Decimal] = []
    tiers: List[str] = []
    ota_collecting_count = 0

    for item in line_items:
        t = item["epistemic_tier"]
        tiers.append(t)
        if item["lifecycle_status"] == "OTA_COLLECTING":
            ota_collecting_count += 1
            # Still accumulate gross/commission for full line-item visibility,
            # but DON'T include in net_vals (payout not yet received).
        if not is_multi_currency:
            g = item["gross"]
            c = item["ota_commission"]
            n = item["net_to_property"]
            if g is not None:
                gross_vals.append(Decimal(g))
            if c is not None:
                commission_vals.append(Decimal(c))
            if n is not None and item["lifecycle_status"] != "OTA_COLLECTING":
                net_vals.append(Decimal(n))

    if is_multi_currency:
        gross_total = None
        commission_total = None
        net_to_property_total = None
        management_fee_amount = None
        owner_net_total = None
    else:
        gross_total = sum(gross_vals, Decimal("0")) if gross_vals else None
        commission_total = sum(commission_vals, Decimal("0")) if commission_vals else None
        net_to_prop = sum(net_vals, Decimal("0")) if net_vals else None

        if net_to_prop is not None and mgmt_fee_pct > Decimal("0"):
            management_fee_amount = (net_to_prop * mgmt_fee_pct / Decimal("100")).quantize(Decimal("0.01"))
            owner_net_total = (net_to_prop - management_fee_amount).quantize(Decimal("0.01"))
        else:
            management_fee_amount = None
            owner_net_total = net_to_prop

        net_to_property_total = net_to_prop

    worst_tier = _worst_tier(tiers) if tiers else "C"

    return {
        "currency": currency,
        "gross_total": _optional_str(gross_total),
        "ota_commission_total": _optional_str(commission_total),
        "net_to_property_total": _optional_str(net_to_property_total),
        "management_fee_pct": _fmt(mgmt_fee_pct),
        "management_fee_amount": _optional_str(management_fee_amount),
        "owner_net_total": _optional_str(owner_net_total),
        "booking_count": len(line_items),
        "ota_collecting_excluded_from_net": ota_collecting_count,
        "overall_epistemic_tier": worst_tier,
    }


def _render_pdf_text(
    property_id: str,
    month: str,
    tenant_id: str,
    summary: Dict[str, Any],
    line_items: List[Dict[str, Any]],
) -> str:
    """
    Render a plain-text owner statement (Phase 121 PDF export contract).
    Returns a UTF-8 string. No external library required.
    """
    sep = "=" * 60
    lines = [
        sep,
        "  OWNER STATEMENT",
        sep,
        f"  Property:  {property_id}",
        f"  Period:    {month}",
        f"  Tenant:    {tenant_id}",
        f"  Currency:  {summary['currency']}",
        f"  Tier:      {summary['overall_epistemic_tier']}",
        "",
        "  BOOKING LINE ITEMS",
        "-" * 60,
    ]

    for item in line_items:
        lines.append(
            f"  {item['booking_id']:<30}  "
            f"{item['provider']:<12}  "
            f"Gross: {item['gross'] or 'N/A':>10}  "
            f"Net: {item['net_to_property'] or 'N/A':>10}  "
            f"Tier:{item['epistemic_tier']}  "
            f"Status:{item['lifecycle_status']}"
        )

    lines += [
        "-" * 60,
        "  SUMMARY",
        "-" * 60,
        f"  Bookings:            {summary['booking_count']}",
        f"  Gross total:         {summary.get('gross_total') or 'N/A'}",
        f"  OTA commission:      {summary.get('ota_commission_total') or 'N/A'}",
        f"  Net to property:     {summary.get('net_to_property_total') or 'N/A'}",
        f"  Management fee ({summary['management_fee_pct']}%): "
        f"{summary.get('management_fee_amount') or 'N/A'}",
        f"  OWNER NET TOTAL:     {summary.get('owner_net_total') or 'N/A'}",
        f"  OTA collecting (excluded from net): "
        f"{summary['ota_collecting_excluded_from_net']}",
        sep,
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# GET /owner-statement/{property_id}
# ---------------------------------------------------------------------------

@router.get(
    "/owner-statement/{property_id}",
    tags=["owner-statement"],
    summary="Monthly owner statement for a property with per-booking line items and management fee",
    responses={
        200: {"description": "Monthly owner statement with per-booking line items"},
        400: {"description": "Missing or malformed 'month' or 'management_fee_pct' query parameter"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "No financial records found for this property + month"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_owner_statement(
    property_id: str,
    month: Optional[str] = Query(default=None, description="Statement month (YYYY-MM)"),
    management_fee_pct: Optional[str] = Query(
        default=None,
        description="Management fee percentage to deduct from net (0.0–100.0). Default: 0 (no fee).",
    ),
    format: Optional[str] = Query(
        default=None,
        description="Response format. Set to 'pdf' for plain-text statement export.",
    ),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> Any:
    """
    Return a monthly financial owner statement for a property.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Path parameters:**
    - `property_id` — the property to generate the statement for.

    **Query parameters:**
    - `month` *(required)* — calendar month in `YYYY-MM` format.
    - `management_fee_pct` *(optional)* — management fee percentage (0.0–100.0).
      Deducted from `net_to_property` to produce `owner_net_total`.
    - `format` *(optional)* — set to `pdf` for plain-text statement output.

    **Per-booking line items** include:
    - `booking_id`, `provider`, `currency`, `check_in`, `check_out`
    - `gross`, `ota_commission`, `net_to_property` (all strings, 2dp)
    - `epistemic_tier` (A/B/C), `lifecycle_status`, `event_kind`

    **Summary** includes:
    - `gross_total`, `ota_commission_total`, `net_to_property_total` (before fee)
    - `management_fee_pct`, `management_fee_amount`
    - `owner_net_total` = net_to_property_total − management_fee_amount
    - `overall_epistemic_tier` (worst tier wins)
    - `ota_collecting_excluded_from_net` count

    **Source:** Reads from `booking_financial_facts` only.
    Never reads `booking_state`.

    **Honesty rule:** `OTA_COLLECTING` bookings appear in line items
    but their net is excluded from `owner_net_total`.
    """
    # --- Validate month ---
    if not month or not _MONTH_RE.match(month):
        return make_error_response(
            status_code=400,
            code=ErrorCode.INVALID_MONTH,
        )

    # --- Validate management_fee_pct ---
    mgmt_fee = _parse_mgmt_fee(management_fee_pct)
    if mgmt_fee is None:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            message="management_fee_pct must be a number between 0.0 and 100.0",
        )

    try:
        db = client if client is not None else _get_supabase_client()
        month_start, month_end = _month_bounds(month)

        # Query: filter by tenant_id AND property_id AND month range
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

        # Dedup: most-recent recorded_at per booking_id
        deduped = _dedup_latest(rows)

        if not deduped:
            return make_error_response(
                status_code=404,
                code=ErrorCode.PROPERTY_NOT_FOUND,
                extra={"property_id": property_id, "month": month},
            )

        # Build line items
        line_items = [_build_line_item(row) for row in deduped]

        # Build summary
        summary = _compute_summary(line_items, mgmt_fee)

        # PDF export path
        if format and format.lower() == "pdf":
            text = _render_pdf_text(property_id, month, tenant_id, summary, line_items)
            return Response(
                content=text.encode("utf-8"),
                media_type="text/plain",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="owner-statement-{property_id}-{month}.txt"'
                    )
                },
            )

        # JSON response
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "property_id": property_id,
                "month": month,
                "total_bookings_checked": len(deduped),
                "summary": summary,
                "line_items": line_items,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /owner-statement/%s error: %s", property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
