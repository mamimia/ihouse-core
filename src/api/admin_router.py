"""
Phase 72 — Tenant Summary Dashboard
Phase 82 — Admin Query API (metrics, DLQ, provider health, booking timeline)
Phase 110 — OTA Reconciliation API

Endpoints:
  GET /admin/summary               — tenant operational summary (Phase 72)
  GET /admin/metrics               — idempotency + DLQ metrics (Phase 82)
  GET /admin/dlq                   — DLQ pending + rejection breakdown (Phase 82)
  GET /admin/health/providers      — per-provider last ingest status (Phase 82)
  GET /admin/bookings/{id}/timeline — per-booking event timeline from event_log (Phase 82)
  GET /admin/reconciliation        — offline reconciliation report (Phase 110)

Rules:
- JWT auth required on all endpoints.
- All queries are tenant-scoped where applicable.
- Read-only. No writes to any table.
- DLQ endpoints are global (ota_dead_letter has no tenant_id).

Invariant:
  These endpoints must NEVER write to any table.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# Known OTA providers — used for health/providers response
_KNOWN_PROVIDERS = ("bookingcom", "airbnb", "expedia", "agoda", "tripcom")

# DLQ replay statuses that count as successfully applied
_APPLIED = frozenset({"APPLIED", "ALREADY_APPLIED", "ALREADY_EXISTS", "ALREADY_EXISTS_BUSINESS"})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Query helpers — each returns a single scalar, never raises
# ---------------------------------------------------------------------------

def _count_bookings_by_status(db: Any, tenant_id: str, status: str) -> int:
    result = (
        db.table("booking_state")
        .select("booking_id")
        .eq("tenant_id", tenant_id)
        .eq("status", status)
        .execute()
    )
    return len(result.data or [])


def _count_total_bookings(db: Any, tenant_id: str) -> int:
    result = (
        db.table("booking_state")
        .select("booking_id")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    return len(result.data or [])


def _count_dlq_pending(db: Any) -> int:
    """
    DLQ pending count — global (ota_dead_letter has no tenant_id).
    A row is pending if replay_result is NULL or not an APPLIED status.
    """
    result = db.table("ota_dead_letter").select("id, replay_result").execute()
    return sum(
        1 for r in (result.data or [])
        if r.get("replay_result") not in _APPLIED
    )


def _count_amendments(db: Any, tenant_id: str) -> int:
    """
    Count BOOKING_AMENDED events for this tenant from booking_financial_facts.
    Each recorded amendment generates a row with event_kind='BOOKING_AMENDED'.
    """
    result = (
        db.table("booking_financial_facts")
        .select("id")
        .eq("tenant_id", tenant_id)
        .eq("event_kind", "BOOKING_AMENDED")
        .execute()
    )
    return len(result.data or [])


def _last_event_at(db: Any, tenant_id: str) -> Optional[str]:
    """Return updated_at of the most recently modified booking, or None."""
    result = (
        db.table("booking_state")
        .select("updated_at")
        .eq("tenant_id", tenant_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["updated_at"] if rows else None


def _get_provider_health(db: Any, tenant_id: str) -> list:
    """
    Return per-provider last ingest timestamp from event_log (tenant-scoped).
    Returns a list of dicts: {provider, last_ingest_at, status}.
    status: 'ok' = data found, 'unknown' = no events for this provider.
    Never raises.
    """
    providers = []
    for provider in _KNOWN_PROVIDERS:
        try:
            result = (
                db.table("event_log")
                .select("recorded_at")
                .eq("tenant_id", tenant_id)
                .eq("source", provider)
                .order("recorded_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                last_at = rows[0].get("recorded_at")
                providers.append({"provider": provider, "last_ingest_at": last_at, "status": "ok"})
            else:
                providers.append({"provider": provider, "last_ingest_at": None, "status": "unknown"})
        except Exception:  # noqa: BLE001
            providers.append({"provider": provider, "last_ingest_at": None, "status": "unknown"})
    return providers


def _get_booking_timeline(db: Any, tenant_id: str, booking_id: str) -> list:
    """
    Return ordered list of events for a booking from event_log.
    Filters by tenant_id + booking_id (from payload->booking_id).
    Returns list of dicts: {event_kind, occurred_at, recorded_at, envelope_id}.
    Never raises.
    """
    try:
        result = (
            db.table("event_log")
            .select("event_kind, occurred_at, recorded_at, envelope_id")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("recorded_at", desc=False)
            .execute()
        )
        rows = result.data or []
        return [
            {
                "event_kind": r.get("event_kind"),
                "occurred_at": r.get("occurred_at"),
                "recorded_at": r.get("recorded_at"),
                "envelope_id": r.get("envelope_id"),
            }
            for r in rows
        ]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# GET /admin/summary (Phase 72)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/summary",
    tags=["admin"],
    summary="Tenant operational summary",
    responses={
        200: {"description": "Operational summary for the authenticated tenant"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_tenant_summary(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns a real-time operational summary for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Scope:** All data is scoped to the authenticated tenant.
    DLQ pending count is global (shared infrastructure metric).

    **Source tables:**
    - `booking_state` — active/canceled counts, last event
    - `ota_dead_letter` — DLQ pending (global)
    - `booking_financial_facts` — amendment count (tenant-scoped)
    """
    try:
        db = client if client is not None else _get_supabase_client()

        active = _count_bookings_by_status(db, tenant_id, "active")
        canceled = _count_bookings_by_status(db, tenant_id, "canceled")
        total = _count_total_bookings(db, tenant_id)
        dlq_pending = _count_dlq_pending(db)
        amendment_count = _count_amendments(db, tenant_id)
        last_at = _last_event_at(db, tenant_id)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "active_bookings": active,
                "canceled_bookings": canceled,
                "total_bookings": total,
                "dlq_pending": dlq_pending,
                "amendment_count": amendment_count,
                "last_event_at": last_at,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/summary error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/metrics (Phase 82)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/metrics",
    tags=["admin"],
    summary="Idempotency and DLQ metrics",
    responses={
        200: {"description": "Idempotency and DLQ health metrics"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_admin_metrics(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns idempotency health metrics from DLQ and ordering buffer.

    **Authentication:** Bearer JWT required.

    **Source tables:**
    - `ota_dead_letter` — DLQ counts (global)
    - `ota_ordering_buffer` — ordering buffer depth (global)
    """
    try:
        from adapters.ota.idempotency_monitor import collect_idempotency_report  # type: ignore[import]
        db = client if client is not None else _get_supabase_client()
        report = collect_idempotency_report(client=db)
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "total_dlq_rows": report.total_dlq_rows,
                "pending_dlq_rows": report.pending_dlq_rows,
                "already_applied_count": report.already_applied_count,
                "idempotency_rejection_count": report.idempotency_rejection_count,
                "ordering_buffer_depth": report.ordering_buffer_depth,
                "checked_at": report.checked_at,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/metrics error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/dlq (Phase 82)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/dlq",
    tags=["admin"],
    summary="DLQ pending rows and rejection breakdown",
    responses={
        200: {"description": "DLQ pending count and rejection breakdown"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_admin_dlq(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns DLQ pending count, replayed count, and rejection breakdown.

    **Authentication:** Bearer JWT required.

    **Note:** DLQ is global — ota_dead_letter has no tenant_id column.
    The authenticated tenant_id is returned for context only.

    **Source tables:**
    - `ota_dead_letter` — pending/replayed counts
    - `ota_dlq_summary` — rejection breakdown view
    """
    try:
        from adapters.ota.dlq_inspector import (  # type: ignore[import]
            get_pending_count,
            get_replayed_count,
            get_rejection_breakdown,
        )
        db = client if client is not None else _get_supabase_client()
        pending = get_pending_count(client=db)
        replayed = get_replayed_count(client=db)
        breakdown = get_rejection_breakdown(client=db)
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "pending": pending,
                "replayed": replayed,
                "breakdown": breakdown,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/dlq error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/health/providers (Phase 82)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/health/providers",
    tags=["admin"],
    summary="Per-provider last ingest status",
    responses={
        200: {"description": "Per-provider last ingest timestamp and status"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_provider_health(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the last successful ingest timestamp per OTA provider for this tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only events belonging to this tenant are considered.

    **Providers checked:** bookingcom, airbnb, expedia, agoda, tripcom.

    **Status values:**
    - `ok` — at least one event found for this provider
    - `unknown` — no events found (provider may be unconfigured)

    **Source:** `event_log` — read-only.
    """
    try:
        db = client if client is not None else _get_supabase_client()
        providers = _get_provider_health(db, tenant_id)
        checked_at = datetime.now(tz=timezone.utc).isoformat()
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "providers": providers,
                "checked_at": checked_at,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/health/providers error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/bookings/{booking_id}/timeline (Phase 82)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/bookings/{booking_id}/timeline",
    tags=["admin"],
    summary="Per-booking event timeline",
    responses={
        200: {"description": "Ordered event timeline for a booking from event_log"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "No events found for this booking_id"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_booking_timeline(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the full ordered event history for a booking from event_log.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only events for this tenant's bookings are returned.
    Cross-tenant reads return 404, not 403, to avoid leaking booking existence.

    **Source:** `event_log` — the canonical source of truth. Read-only.

    **Ordering:** Events are ordered by `recorded_at` ascending (earliest first).
    """
    try:
        db = client if client is not None else _get_supabase_client()
        events = _get_booking_timeline(db, tenant_id, booking_id)
        if not events:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"booking_id": booking_id},
            )
        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "tenant_id": tenant_id,
                "events": events,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/bookings/%s/timeline error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/reconciliation (Phase 110)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/reconciliation",
    tags=["admin"],
    summary="Offline reconciliation report",
    responses={
        200: {"description": "ReconciliationSummary (+ findings if include_findings=true)"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_reconciliation(
    include_findings: bool = False,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Run the offline reconciliation detector and return a summary report.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only this tenant's bookings are checked.

    **Query parameters:**
    - `include_findings` — if `true`, the full findings list is included in
      the response. Default `false` (summary only) for performance.

    **What is checked (offline, no OTA API):**
    - `FINANCIAL_FACTS_MISSING` — bookings in `booking_state` with no row
      in `booking_financial_facts`
    - `STALE_BOOKING` — active bookings not updated in > 30 days

    **What requires a live OTA snapshot (not yet implemented):**
    - BOOKING_MISSING_INTERNALLY, BOOKING_STATUS_MISMATCH, DATE_MISMATCH,
      FINANCIAL_AMOUNT_DRIFT, PROVIDER_DRIFT

    **Source tables:** `booking_state`, `booking_financial_facts` — read-only.

    **Invariant:** Never writes to any table. Never bypasses apply_envelope.
    """
    try:
        from adapters.ota.reconciliation_detector import run_reconciliation  # type: ignore[import]
        from adapters.ota.reconciliation_model import ReconciliationSummary  # type: ignore[import]

        db = client if client is not None else _get_supabase_client()
        report = run_reconciliation(tenant_id=tenant_id, db=db)
        summary = ReconciliationSummary.from_report(report)

        content: dict = {
            "tenant_id":       summary.tenant_id,
            "generated_at":    summary.generated_at,
            "total_checked":   report.total_checked,
            "finding_count":   summary.finding_count,
            "critical_count":  summary.critical_count,
            "warning_count":   summary.warning_count,
            "info_count":      summary.info_count,
            "has_critical":    summary.has_critical,
            "has_warnings":    summary.has_warnings,
            "top_kind":        summary.top_kind,
            "partial":         summary.partial,
        }

        if include_findings:
            content["findings"] = [
                {
                    "finding_id":      f.finding_id,
                    "kind":            f.kind.value,
                    "severity":        f.severity.value,
                    "booking_id":      f.booking_id,
                    "provider":        f.provider,
                    "description":     f.description,
                    "detected_at":     f.detected_at,
                    "internal_value":  f.internal_value,
                    "external_value":  f.external_value,
                    "correction_hint": f.correction_hint,
                }
                for f in report.findings
            ]

        return JSONResponse(status_code=200, content=content)

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/reconciliation error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
