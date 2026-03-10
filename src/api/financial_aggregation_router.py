"""
Phase 116 — Financial Aggregation API (Ring 1)
Phase 161 — Multi-Currency Conversion Layer
Phase 166 — Owner Property Scoping

Aggregation endpoints over booking_financial_facts for the authenticated tenant.

Endpoints:
    GET /financial/summary?period=YYYY-MM[&base_currency=USD]
        Gross + commission + net totals, grouped by currency.
        If base_currency supplied, all buckets are converted to that currency.

    GET /financial/by-provider?period=YYYY-MM[&base_currency=USD]
        Per-OTA-provider breakdown, grouped by currency.

    GET /financial/by-property?period=YYYY-MM[&base_currency=USD]
        Per-property breakdown, grouped by currency.

    GET /financial/lifecycle-distribution?period=YYYY-MM
        Count of bookings by PaymentLifecycleStatus.

Rules:
- JWT auth required on all endpoints.
- Tenant isolation enforced at DB level (.eq("tenant_id", tenant_id)).
- Reads from booking_financial_facts only. Never reads booking_state.
- Multi-currency: no cross-currency aggregation is ever performed.
  Each currency bucket is independent. USD + EUR are never summed.
- period param is required, must be YYYY-MM format.
- Only bookings with event_kind='BOOKING_CREATED' are included in totals,
  unless the booking also has a BOOKING_AMENDED row (in which case the
  most-recent row per booking_id is used — deduped in Python).
- Monetary fields are returned as strings to preserve Decimal precision.
- NULL monetary values from the DB are treated as 0.00 in aggregation.

Invariant (Phase 62+):
  These endpoints must NEVER read from or write to booking_state.

Multi-currency invariant (Phase 116):
  Amounts in different currencies MUST NEVER be summed together.
  Each currency is returned as a separate key in the response.

Supported currencies (Phase 116):
  USD, THB, EUR, GBP, CNY, INR, JPY, SGD, AUD, ILS, BRL, MXN, HKD,
  AED, IDR, CAD, TRY, KRW, CHF
  All other currencies found in data are grouped under "OTHER".
"""
from __future__ import annotations

import logging
import os
import re
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
# Constants
# ---------------------------------------------------------------------------

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Currencies supported out of the box (Phase 116).
# Any currency NOT in this set is aggregated as "OTHER".
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({
    "USD",  # US Dollar          — global
    "THB",  # Thai Baht          — Southeast Asia
    "EUR",  # Euro               — Europe
    "GBP",  # British Pound      — UK
    "CNY",  # Chinese Yuan       — China
    "INR",  # Indian Rupee       — India
    "JPY",  # Japanese Yen       — Japan
    "SGD",  # Singapore Dollar   — Singapore / regional hub
    "AUD",  # Australian Dollar  — Australia / Pacific
    "ILS",  # Israeli New Shekel — Israel
    "BRL",  # Brazilian Real      — Brazil / Latin America
    "MXN",  # Mexican Peso        — Mexico / Latin America
    "HKD",  # Hong Kong Dollar    — Hong Kong / regional hub
    "AED",  # UAE Dirham          — Dubai / UAE (top short-term rental market)
    "IDR",  # Indonesian Rupiah   — Indonesia / Bali (top Airbnb destination)
    "CAD",  # Canadian Dollar     — Canada (Toronto, Vancouver, Montreal)
    "TRY",  # Turkish Lira        — Turkey / Istanbul (top-5 Airbnb city globally)
    "KRW",  # South Korean Won    — South Korea / Seoul
    "CHF",  # Swiss Franc         — Switzerland (luxury short-term rentals)
})


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

def _to_decimal(value: Any) -> Decimal:
    """Convert a DB value to Decimal. Returns Decimal('0') on None / invalid."""
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _canonical_currency(currency: Optional[str]) -> str:
    """Return the currency code if supported, otherwise 'OTHER'."""
    if currency and currency.upper() in SUPPORTED_CURRENCIES:
        return currency.upper()
    return "OTHER"


def _fmt(d: Decimal) -> str:
    """Format Decimal to 2 decimal places string (for JSON serialisation)."""
    return str(d.quantize(Decimal("0.01")))


def _month_bounds(period: str) -> tuple[str, str]:
    """Return (month_start, month_end_exclusive) strings for a YYYY-MM period."""
    year, mon = int(period[:4]), int(period[5:])
    month_start = f"{period}-01"
    if mon == 12:
        month_end = f"{year + 1}-01-01"
    else:
        month_end = f"{year}-{mon + 1:02d}-01"
    return month_start, month_end


def _dedup_latest(rows: List[dict]) -> List[dict]:
    """
    Deduplicate rows by booking_id — keep the most-recent recorded_at per booking.
    This ensures BOOKING_AMENDED rows supersede BOOKING_CREATED rows for the
    same booking when aggregating totals.
    """
    latest: Dict[str, dict] = {}
    for row in rows:
        bid = row.get("booking_id", "")
        existing = latest.get(bid)
        if existing is None:
            latest[bid] = row
        else:
            # Keep the row with the later recorded_at (string comparison works for ISO dates)
            if (row.get("recorded_at") or "") > (existing.get("recorded_at") or ""):
                latest[bid] = row
    return list(latest.values())


def _validate_period(period: Optional[str]) -> Optional[JSONResponse]:
    """Return an error JSONResponse if period is invalid, else None."""
    if period is None:
        return make_error_response(
            status_code=400,
            code=ErrorCode.INVALID_PERIOD,
            extra={"detail": "period query parameter is required (format: YYYY-MM)"},
        )
    if not _MONTH_RE.match(period):
        return make_error_response(
            status_code=400,
            code=ErrorCode.INVALID_PERIOD,
            extra={"detail": "period must be in YYYY-MM format (e.g. 2026-03)"},
        )
    return None


def _fetch_period_rows(
    db: Any,
    tenant_id: str,
    period: str,
    property_ids: Optional[List[str]] = None,
) -> List[dict]:
    """Fetch all booking_financial_facts rows for the tenant + period.

    Phase 166: if property_ids is provided (non-None, non-empty), only rows
    matching those property IDs are returned.
    """
    month_start, month_end = _month_bounds(period)
    query = (
        db.table("booking_financial_facts")
        .select("*")
        .eq("tenant_id", tenant_id)
        .gte("recorded_at", month_start)
        .lt("recorded_at", month_end)
        .order("recorded_at", desc=False)
    )
    if property_ids is not None and len(property_ids) > 0:
        query = query.in_("property_id", property_ids)
    result = query.execute()
    return result.data or []


def _get_owner_property_filter(
    db: Any,
    tenant_id: str,
    user_id: Optional[str],
) -> Optional[List[str]]:
    """Phase 166: return the list of allowed property_ids for an owner role caller.

    Returns:
        - None  → no restriction (admin / manager / no record)
        - list  → caller is 'owner'; restrict to these property_ids
    Best-effort: returns None on any error.
    """
    if not user_id:
        return None
    try:
        from api.permissions_router import get_permission_record  # lazy import
        perm = get_permission_record(db, tenant_id, user_id)
        if perm and perm.get("role") == "owner":
            allowed = (perm.get("permissions") or {}).get("property_ids", [])
            return allowed if isinstance(allowed, list) else []
    except Exception:  # noqa: BLE001
        pass
    return None


def _validate_base_currency(base_currency: Optional[str]) -> Optional[JSONResponse]:
    """Return error response if base_currency is supplied but not a known currency code."""
    if base_currency is None:
        return None
    if not base_currency.isalpha() or len(base_currency) != 3:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "base_currency must be a 3-letter ISO currency code (e.g. USD, THB)"},
        )
    return None


def _fetch_rate(db: Any, from_ccy: str, to_ccy: str) -> Optional[Decimal]:
    """
    Look up an exchange rate from the exchange_rates table.
    Returns None if no rate row exists for this pair.
    Same currency pair always returns Decimal('1').
    """
    if from_ccy.upper() == to_ccy.upper():
        return Decimal("1")
    try:
        result = (
            db.table("exchange_rates")
            .select("rate")
            .eq("from_currency", from_ccy.upper())
            .eq("to_currency", to_ccy.upper())
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            return _to_decimal(rows[0]["rate"])
        return None
    except Exception:
        return None


def _apply_conversion(
    amounts: Dict[str, Dict[str, Any]],
    base_currency: str,
    db: Any,
) -> tuple[Dict[str, Dict[str, Any]], list[str]]:
    """
    Convert all currency buckets in `amounts` to `base_currency`.

    Returns:
        (merged_amounts, warnings)
        - merged_amounts: all values collapsed into one currency key
        - warnings: list of currency codes for which no rate was found
    """
    target = base_currency.upper()
    merged: Dict[str, Any] = {
        "gross": Decimal("0"),
        "commission": Decimal("0"),
        "net": Decimal("0"),
        "booking_count": 0,
    }
    warnings: list[str] = []

    for ccy, data in amounts.items():
        rate = _fetch_rate(db, ccy, target)
        if rate is None:
            warnings.append(ccy)
            # Still include unconverted amounts under original currency in a passthrough sense
            # — they are excluded from the converted total with a warning
            continue
        merged["gross"] += _to_decimal(data["gross"]) * rate
        merged["commission"] += _to_decimal(data["commission"]) * rate
        merged["net"] += _to_decimal(data["net"]) * rate
        merged["booking_count"] += data["booking_count"]

    out = {
        target: {
            "gross": _fmt(merged["gross"]),
            "commission": _fmt(merged["commission"]),
            "net": _fmt(merged["net"]),
            "booking_count": merged["booking_count"],
        }
    }
    return out, warnings


# ---------------------------------------------------------------------------
# GET /financial/summary
# ---------------------------------------------------------------------------

@router.get(
    "/financial/summary",
    tags=["financial"],
    summary="Financial summary totals for the period, grouped by currency",
    responses={
        200: {"description": "Gross, commission, and net totals by currency"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_financial_summary(
    period: Optional[str] = None,
    base_currency: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Aggregate financial totals for the authenticated tenant for the given month.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    Per-currency breakdown of `gross`, `commission`, `net`, and `booking_count`.

    **Multi-currency rule:**
    Amounts in different currencies are never combined. Each currency is a
    separate key. Bookings with unknown or null currency appear in `"OTHER"`.

    **Deduplication:**
    The most recent financial record per booking is used, so BOOKING_AMENDED
    rows naturally supersede BOOKING_CREATED rows for the same booking.

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err
    err2 = _validate_base_currency(base_currency)
    if err2:
        return err2

    try:
        db = client if client is not None else _get_supabase_client()
        property_ids = _get_owner_property_filter(db, tenant_id, user_id)
        rows = _fetch_period_rows(db, tenant_id, period, property_ids)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        # Aggregate per currency
        totals: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"gross": Decimal("0"), "commission": Decimal("0"), "net": Decimal("0"), "booking_count": 0}
        )
        for row in deduped:
            cur = _canonical_currency(row.get("currency"))
            totals[cur]["gross"] += _to_decimal(row.get("total_price"))
            totals[cur]["commission"] += _to_decimal(row.get("ota_commission"))
            totals[cur]["net"] += _to_decimal(row.get("net_to_property"))
            totals[cur]["booking_count"] += 1

        currencies_out = {
            cur: {
                "gross": _fmt(data["gross"]),
                "commission": _fmt(data["commission"]),
                "net": _fmt(data["net"]),
                "booking_count": data["booking_count"],
            }
            for cur, data in sorted(totals.items())
        }

        # Phase 161: optional conversion to base_currency
        conversion_warnings: list[str] = []
        if base_currency:
            currencies_out, conversion_warnings = _apply_conversion(
                {cur: {"gross": _fmt(data["gross"]), "commission": _fmt(data["commission"]),
                       "net": _fmt(data["net"]), "booking_count": data["booking_count"]}
                 for cur, data in totals.items()},
                base_currency,
                db,
            )

        response_body: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "period": period,
            "total_bookings": len(deduped),
            "currencies": currencies_out,
        }
        if base_currency:
            response_body["base_currency"] = base_currency.upper()
        if conversion_warnings:
            response_body["conversion_warnings"] = conversion_warnings

        return JSONResponse(status_code=200, content=response_body)

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /financial/summary error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /financial/by-provider
# ---------------------------------------------------------------------------

@router.get(
    "/financial/by-provider",
    tags=["financial"],
    summary="Financial breakdown by OTA provider for the period",
    responses={
        200: {"description": "Per-provider financial totals grouped by currency"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_financial_by_provider(
    period: Optional[str] = None,
    base_currency: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Per-OTA-provider financial breakdown for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    Per-provider, per-currency breakdown of `gross`, `commission`, `net`,
    and `booking_count`.

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err
    err2 = _validate_base_currency(base_currency)
    if err2:
        return err2

    try:
        db = client if client is not None else _get_supabase_client()
        property_ids = _get_owner_property_filter(db, tenant_id, user_id)
        rows = _fetch_period_rows(db, tenant_id, period, property_ids)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        # Aggregate per (provider, currency)
        by_provider: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"gross": Decimal("0"), "commission": Decimal("0"), "net": Decimal("0"), "booking_count": 0}
            )
        )
        for row in deduped:
            provider = row.get("provider") or "unknown"
            cur = _canonical_currency(row.get("currency"))
            by_provider[provider][cur]["gross"] += _to_decimal(row.get("total_price"))
            by_provider[provider][cur]["commission"] += _to_decimal(row.get("ota_commission"))
            by_provider[provider][cur]["net"] += _to_decimal(row.get("net_to_property"))
            by_provider[provider][cur]["booking_count"] += 1

        providers_out: Dict[str, Any] = {
            prov: {
                cur: {
                    "gross": _fmt(data["gross"]),
                    "commission": _fmt(data["commission"]),
                    "net": _fmt(data["net"]),
                    "booking_count": data["booking_count"],
                }
                for cur, data in sorted(cur_map.items())
            }
            for prov, cur_map in sorted(by_provider.items())
        }

        # Phase 161: optional conversion per provider
        all_warnings: list[str] = []
        if base_currency:
            converted_providers: Dict[str, Any] = {}
            for prov, cur_map in by_provider.items():
                str_map = {
                    cur: {"gross": _fmt(d["gross"]), "commission": _fmt(d["commission"]),
                          "net": _fmt(d["net"]), "booking_count": d["booking_count"]}
                    for cur, d in cur_map.items()
                }
                converted, warns = _apply_conversion(str_map, base_currency, db)
                converted_providers[prov] = converted
                all_warnings.extend(w for w in warns if w not in all_warnings)
            providers_out = converted_providers

        response_body2: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "period": period,
            "providers": providers_out,
        }
        if base_currency:
            response_body2["base_currency"] = base_currency.upper()
        if all_warnings:
            response_body2["conversion_warnings"] = all_warnings

        return JSONResponse(status_code=200, content=response_body2)

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /financial/by-provider error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /financial/by-property
# ---------------------------------------------------------------------------

@router.get(
    "/financial/by-property",
    tags=["financial"],
    summary="Financial breakdown by property for the period",
    responses={
        200: {"description": "Per-property financial totals grouped by currency"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_financial_by_property(
    period: Optional[str] = None,
    base_currency: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Per-property financial breakdown for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    Per-property, per-currency breakdown of `gross`, `commission`, `net`,
    and `booking_count`. Properties are identified by `property_id` from the
    financial facts. Rows missing `property_id` appear under `"unknown"`.

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err
    err2 = _validate_base_currency(base_currency)
    if err2:
        return err2

    try:
        db = client if client is not None else _get_supabase_client()
        property_ids = _get_owner_property_filter(db, tenant_id, user_id)
        rows = _fetch_period_rows(db, tenant_id, period, property_ids)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        # Aggregate per (property_id, currency)
        by_property: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
            lambda: defaultdict(
                lambda: {"gross": Decimal("0"), "commission": Decimal("0"), "net": Decimal("0"), "booking_count": 0}
            )
        )
        for row in deduped:
            prop = row.get("property_id") or "unknown"
            cur = _canonical_currency(row.get("currency"))
            by_property[prop][cur]["gross"] += _to_decimal(row.get("total_price"))
            by_property[prop][cur]["commission"] += _to_decimal(row.get("ota_commission"))
            by_property[prop][cur]["net"] += _to_decimal(row.get("net_to_property"))
            by_property[prop][cur]["booking_count"] += 1

        properties_out: Dict[str, Any] = {
            prop: {
                cur: {
                    "gross": _fmt(data["gross"]),
                    "commission": _fmt(data["commission"]),
                    "net": _fmt(data["net"]),
                    "booking_count": data["booking_count"],
                }
                for cur, data in sorted(cur_map.items())
            }
            for prop, cur_map in sorted(by_property.items())
        }

        # Phase 161: optional conversion per property
        prop_warnings: list[str] = []
        if base_currency:
            converted_props: Dict[str, Any] = {}
            for prop, cur_map in by_property.items():
                str_map = {
                    cur: {"gross": _fmt(d["gross"]), "commission": _fmt(d["commission"]),
                          "net": _fmt(d["net"]), "booking_count": d["booking_count"]}
                    for cur, d in cur_map.items()
                }
                converted, warns = _apply_conversion(str_map, base_currency, db)
                converted_props[prop] = converted
                prop_warnings.extend(w for w in warns if w not in prop_warnings)
            properties_out = converted_props

        response_body3: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "period": period,
            "properties": properties_out,
        }
        if base_currency:
            response_body3["base_currency"] = base_currency.upper()
        if prop_warnings:
            response_body3["conversion_warnings"] = prop_warnings

        return JSONResponse(status_code=200, content=response_body3)

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /financial/by-property error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /financial/lifecycle-distribution
# ---------------------------------------------------------------------------

@router.get(
    "/financial/lifecycle-distribution",
    tags=["financial"],
    summary="Distribution of bookings by PaymentLifecycleStatus for the period",
    responses={
        200: {"description": "Count of bookings per PaymentLifecycleStatus"},
        400: {"description": "Missing or invalid period parameter"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_lifecycle_distribution(
    period: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Count bookings by PaymentLifecycleStatus for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Query parameters:**
    - `period` *(required)* — calendar month in `YYYY-MM` format.

    **Returns:**
    Distribution dict mapping each `PaymentLifecycleStatus` value to a count.
    The lifecycle projection is computed in-memory using the same rules as
    `GET /payment-status/{booking_id}` (Phase 103).

    Possible status values:
    `GUEST_PAID`, `OTA_COLLECTING`, `PAYOUT_PENDING`, `PAYOUT_RELEASED`,
    `RECONCILIATION_PENDING`, `OWNER_NET_PENDING`, `UNKNOWN`

    **Source:** Reads from `booking_financial_facts` only.
    """
    err = _validate_period(period)
    if err:
        return err

    try:
        from adapters.ota.payment_lifecycle import project_payment_lifecycle  # type: ignore[import]

        db = client if client is not None else _get_supabase_client()
        rows = _fetch_period_rows(db, tenant_id, period)  # type: ignore[arg-type]
        deduped = _dedup_latest(rows)

        distribution: Dict[str, int] = defaultdict(int)
        for row in deduped:
            status = project_payment_lifecycle(row).value
            distribution[status] += 1

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "period": period,
                "total_bookings": len(deduped),
                "distribution": dict(sorted(distribution.items())),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /financial/lifecycle-distribution error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
