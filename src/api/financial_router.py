"""
Phase 67 — Financial Facts Query API
Phase 108 — Financial List Query API

GET /financial/{booking_id}  — single booking, most-recent financial facts (Phase 67)
GET /financial               — list financial records with filters (Phase 108)

Rules:
- JWT auth required on both endpoints.
- Tenant isolation enforced at DB level (.eq("tenant_id", tenant_id)).
- Reads from booking_financial_facts only. Never reads booking_state.
- Single-booking endpoint returns the most-recent row (ORDER BY recorded_at DESC LIMIT 1).
- List endpoint returns all matching rows ordered by recorded_at DESC, limit-clamped.

Invariant (locked Phase 62+):
  These endpoints must NEVER read from or write to booking_state.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /financial/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/financial/{booking_id}",
    tags=["financial"],
    summary="Get financial facts for a booking",
    responses={
        200: {"description": "Financial facts for the booking (most recent record)"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "No financial facts found for this booking_id"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_financial_facts(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return the most recent financial facts for a given booking.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only financial records belonging to the requesting
    tenant are returned. Cross-tenant reads return 404, not 403, to avoid
    leaking booking existence information.

    **Source:** Reads from `booking_financial_facts` projection table only.
    Never touches `booking_state`.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )

        if not result.data:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"booking_id": booking_id},
            )

        row = result.data[0]
        return JSONResponse(
            status_code=200,
            content={
                "booking_id": row["booking_id"],
                "tenant_id": row["tenant_id"],
                "provider": row["provider"],
                "total_price": row.get("total_price"),
                "currency": row.get("currency"),
                "ota_commission": row.get("ota_commission"),
                "taxes": row.get("taxes"),
                "fees": row.get("fees"),
                "net_to_property": row.get("net_to_property"),
                "source_confidence": row["source_confidence"],
                "event_kind": row["event_kind"],
                "recorded_at": row["recorded_at"],
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /financial/%s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /financial  (Phase 108)
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402

_MONTH_RE = _re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


@router.get(
    "/financial",
    tags=["financial"],
    summary="List financial records for a tenant",
    responses={
        200: {"description": "List of financial fact records from booking_financial_facts"},
        400: {"description": "Invalid query parameter (e.g. bad month format)"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_financial(
    provider: Optional[str] = None,
    month: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return a list of financial fact records from `booking_financial_facts`.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** All results are scoped to the authenticated tenant.

    **Query parameters:**
    - `provider` — filter by OTA provider name, e.g. `bookingcom`, `airbnb` (optional)
    - `month` — filter by calendar month in `YYYY-MM` format, matched against `recorded_at` (optional)
    - `limit` — max results (1–100, default 50)

    **Source:** Reads from `booking_financial_facts` only. Never touches `booking_state`.

    **Invariant:** Read-only. Never writes to any table.
    """
    # Validate month format
    if month is not None and not _MONTH_RE.match(month):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "month must be in YYYY-MM format (e.g. 2026-03)"},
        )

    # Clamp limit
    limit = max(1, min(limit, _MAX_LIMIT))

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("tenant_id", tenant_id)
        )

        if provider is not None:
            query = query.eq("provider", provider)

        if month is not None:
            # recorded_at is a timestamptz; filter rows whose recorded_at falls
            # within the given calendar month using gte/lt bounds.
            month_start = f"{month}-01"
            year, mon = int(month[:4]), int(month[5:])
            if mon == 12:
                next_year, next_mon = year + 1, 1
            else:
                next_year, next_mon = year, mon + 1
            month_end = f"{next_year}-{next_mon:02d}-01"
            query = query.gte("recorded_at", month_start).lt("recorded_at", month_end)

        result = query.order("recorded_at", desc=True).limit(limit).execute()
        rows = result.data or []

        records = [
            {
                "booking_id":       r["booking_id"],
                "tenant_id":        r["tenant_id"],
                "provider":         r["provider"],
                "total_price":      r.get("total_price"),
                "currency":         r.get("currency"),
                "ota_commission":   r.get("ota_commission"),
                "taxes":            r.get("taxes"),
                "fees":             r.get("fees"),
                "net_to_property":  r.get("net_to_property"),
                "source_confidence": r["source_confidence"],
                "event_kind":       r["event_kind"],
                "recorded_at":      r["recorded_at"],
            }
            for r in rows
        ]

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "count":     len(records),
                "limit":     limit,
                "records":   records,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /financial error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /financial/enrich  (Phase 470 — Financial Data Enrichment)
# ---------------------------------------------------------------------------

@router.post(
    "/financial/enrich",
    tags=["financial"],
    summary="Re-extract financial facts for PARTIAL confidence bookings (Phase 470)",
    responses={
        200: {"description": "Enrichment results: how many records were upgraded"},
        401: {"description": "Missing or invalid JWT token"},
        503: {"description": "Supabase not configured"},
    },
)
async def enrich_financial_facts(
    provider: Optional[str] = None,
    limit: int = 50,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Phase 470: Re-extract financial facts for PARTIAL confidence bookings.

    Scans booking_financial_facts for rows with source_confidence=PARTIAL,
    re-reads the raw_financial_fields, re-runs the financial extractor,
    and appends a new row if confidence has improved (PARTIAL → FULL or ESTIMATED).

    Append-only — never mutates existing rows.

    **Query parameters:**
    - `provider` — filter by OTA provider (optional)
    - `limit` — max records to process (1–100, default 50)
    """
    limit = max(1, min(limit, 100))

    try:
        from adapters.ota.financial_extractor import extract_financial_facts
        from adapters.ota.financial_writer import write_financial_facts

        db = client if client is not None else _get_suellen_client()

        # Find PARTIAL rows
        query = (
            db.table("booking_financial_facts")
            .select("booking_id,tenant_id,provider,raw_financial_fields,event_kind,source_confidence")
            .eq("tenant_id", tenant_id)
            .eq("source_confidence", "PARTIAL")
        )
        if provider:
            query = query.eq("provider", provider)
        result = query.order("recorded_at", desc=True).limit(limit).execute()

        rows = result.data or []
        upgraded = 0
        skipped = 0
        errors = 0

        for row in rows:
            try:
                raw = row.get("raw_financial_fields") or {}
                prov = row.get("provider", "")
                booking_id = row.get("booking_id", "")

                # Re-run the financial extractor with stored raw fields
                facts = extract_financial_facts(prov, raw)
                if facts is None:
                    skipped += 1
                    continue

                # Only write if confidence improved
                if facts.source_confidence in ("FULL", "ESTIMATED"):
                    write_financial_facts(
                        booking_id=booking_id,
                        tenant_id=tenant_id,
                        event_kind=f"ENRICHED_FROM_{row.get('event_kind', 'UNKNOWN')}",
                        facts=facts,
                        client=db,
                    )
                    upgraded += 1
                    logger.info(
                        "financial/enrich: upgraded %s from PARTIAL → %s",
                        booking_id, facts.source_confidence,
                    )
                else:
                    skipped += 1
            except Exception as exc:
                logger.warning("financial/enrich: error for %s: %s", row.get("booking_id"), exc)
                errors += 1

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "scanned": len(rows),
                "upgraded": upgraded,
                "skipped": skipped,
                "errors": errors,
            },
        )

    except Exception as exc:
        logger.exception("POST /financial/enrich error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


def _get_suellen_client():
    """Alias for _get_supabase_client (typo-safe)."""
    return _get_supabase_client()


# ---------------------------------------------------------------------------
# GET /financial/confidence-report  (Phase 470)
# ---------------------------------------------------------------------------

@router.get(
    "/financial/confidence-report",
    tags=["financial"],
    summary="Confidence distribution report across all financial records (Phase 470)",
    responses={
        200: {"description": "Confidence breakdown by provider"},
        401: {"description": "Missing or invalid JWT token"},
    },
)
async def confidence_report(
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Phase 470: Report the distribution of source_confidence across all
    financial records for the authenticated tenant.

    Returns confidence counts by provider, useful for monitoring
    data quality and tracking enrichment progress.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_financial_facts")
            .select("provider,source_confidence")
            .eq("tenant_id", tenant_id)
            .execute()
        )

        rows = result.data or []

        # Build distribution: { provider: { FULL: n, PARTIAL: n, ESTIMATED: n } }
        distribution: dict[str, dict[str, int]] = {}
        for row in rows:
            prov = row.get("provider", "unknown")
            conf = row.get("source_confidence", "UNKNOWN")
            if prov not in distribution:
                distribution[prov] = {}
            distribution[prov][conf] = distribution[prov].get(conf, 0) + 1

        totals = {
            "FULL": sum(d.get("FULL", 0) for d in distribution.values()),
            "PARTIAL": sum(d.get("PARTIAL", 0) for d in distribution.values()),
            "ESTIMATED": sum(d.get("ESTIMATED", 0) for d in distribution.values()),
            "OPERATOR_MANUAL": sum(d.get("OPERATOR_MANUAL", 0) for d in distribution.values()),
        }

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "total_records": len(rows),
                "totals": totals,
                "by_provider": distribution,
            },
        )

    except Exception as exc:
        logger.exception("GET /financial/confidence-report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

