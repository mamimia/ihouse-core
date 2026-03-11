"""
Phase 241 — Booking Financial Reconciliation Dashboard API

GET /admin/reconciliation/dashboard

A cross-property aggregate view of the system's reconciliation health.
Unlike the exception inbox (GET /admin/reconciliation?period=YYYY-MM),
which shows individual bookings by month, the dashboard aggregates findings
by property to give a system-wide overview.

Response shape:
    {
        "tenant_id": "...",
        "generated_at": "...",
        "total_bookings_checked": 47,
        "total_findings": 3,
        "findings_by_kind": {
            "FINANCIAL_FACTS_MISSING": 2,
            "STALE_BOOKING": 1
        },
        "by_property": [
            {
                "property_id": "prop_a",
                "findings_count": 2,
                "kinds": ["FINANCIAL_FACTS_MISSING", "STALE_BOOKING"],
                "severity": "HIGH",
                "booking_ids": ["airbnb_abc123"]
            }
        ],
        "partial": false
    }

Severity tiers:
    HIGH   — >= 3 findings on a single property
    MEDIUM — 1-2 findings on a single property
    OK     — 0 findings (not included in by_property)

Architecture invariants:
    - Uses run_reconciliation() — read-only, never bypasses apply_envelope
    - Reads booking_state and booking_financial_facts only
    - Tenant isolation: run_reconciliation scopes by tenant_id
    - JWT auth required
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from adapters.ota.reconciliation_detector import run_reconciliation
from adapters.ota.reconciliation_model import ReconciliationFinding

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Severity calculation
# ---------------------------------------------------------------------------

def _severity(count: int) -> str:
    """Translate a per-property finding count into a human-readable severity."""
    if count >= 3:
        return "HIGH"
    if count >= 1:
        return "MEDIUM"
    return "OK"


# ---------------------------------------------------------------------------
# Build per-property aggregations
# ---------------------------------------------------------------------------

def _aggregate_by_property(
    findings: List[ReconciliationFinding],
) -> List[Dict[str, Any]]:
    """
    Group findings by property_id.

    Since ReconciliationFinding carries only booking_id (not property_id),
    we use booking_id as the grouping key, enriched with provider.
    The property_id field is populated from the source field when available,
    otherwise set to "unknown".

    Returns a list sorted by findings_count descending (worst first).
    """
    # Group finding objects by provider (used as a proxy for property group)
    # In Phase 241 we group by booking_id prefix (source) since property_id
    # is not stored in booking_state — we expose provider-level grouping.
    by_provider: Dict[str, List[ReconciliationFinding]] = defaultdict(list)
    for f in findings:
        key = f.provider or "unknown"
        by_provider[key].append(f)

    result = []
    for provider, group in by_provider.items():
        kinds = sorted({f.kind.value for f in group})
        booking_ids = [f.booking_id for f in group]
        count = len(group)
        result.append(
            {
                "provider": provider,
                "findings_count": count,
                "kinds": kinds,
                "severity": _severity(count),
                "booking_ids": booking_ids,
            }
        )

    # Worst first (most findings then alphabetical provider)
    result.sort(key=lambda x: (-x["findings_count"], x["provider"]))
    return result


def _count_by_kind(findings: List[ReconciliationFinding]) -> Dict[str, int]:
    """Return {kind_value: count} for all findings."""
    counter: Dict[str, int] = {}
    for f in findings:
        key = f.kind.value
        counter[key] = counter.get(key, 0) + 1
    return counter


# ---------------------------------------------------------------------------
# Supabase client helper (mirrors pattern from other admin routers)
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /admin/reconciliation/dashboard
# ---------------------------------------------------------------------------

@router.get(
    "/admin/reconciliation/dashboard",
    tags=["admin"],
    summary="Cross-provider reconciliation health dashboard",
    responses={
        200: {"description": "Aggregate reconciliation findings grouped by provider"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_reconciliation_dashboard(
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Cross-provider reconciliation health dashboard for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **No query parameters required** — scans all bookings for the tenant.

    **Returns:**
    - `total_bookings_checked` — how many booking_state rows were scanned
    - `total_findings` — total findings count across all providers
    - `findings_by_kind` — breakdown by finding type
    - `by_provider` — per-provider aggregation sorted by severity (worst first)
    - `partial` — true if a data source read failed during scan

    **Severity tiers:**
    - `HIGH` — 3 or more findings from a single provider
    - `MEDIUM` — 1–2 findings from a single provider
    """
    try:
        db = _client if _client is not None else _get_supabase_client()
        report = run_reconciliation(tenant_id=tenant_id, db=db)

        by_provider = _aggregate_by_property(report.findings)
        by_kind = _count_by_kind(report.findings)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "generated_at": report.generated_at,
                "total_bookings_checked": report.total_checked,
                "total_findings": len(report.findings),
                "critical_count": report.critical_count,
                "warning_count": report.warning_count,
                "info_count": report.info_count,
                "findings_by_kind": by_kind,
                "by_provider": by_provider,
                "partial": report.partial,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/reconciliation/dashboard error for tenant=%s: %s",
            tenant_id,
            exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
