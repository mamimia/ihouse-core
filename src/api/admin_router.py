"""
Phase 72 — Tenant Summary Dashboard

GET /admin/summary

Returns a real-time operational summary for the authenticated tenant.
All data is scoped to the tenant's JWT sub claim — no cross-tenant data.

Fields returned:
  active_bookings   — booking_state rows with status='active'
  canceled_bookings — booking_state rows with status='canceled'
  total_bookings    — all booking_state rows (active + canceled)
  dlq_pending       — ota_dead_letter rows not yet successfully replayed
  amendment_count   — booking_financial_facts rows with event_kind='BOOKING_AMENDED'
  last_event_at     — most recent updated_at in booking_state (ISO string or null)

Rules:
- JWT auth required.
- All queries are tenant-scoped. Never returns data from other tenants.
- Read-only. No writes.
- On partial failure, returns available data with degraded=true flag.

Invariant:
  This endpoint must NEVER write to any table.
  DLQ counts are global (ota_dead_letter has no tenant_id) — returned as-is.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth

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
    _APPLIED = frozenset({"APPLIED", "ALREADY_APPLIED", "ALREADY_EXISTS", "ALREADY_EXISTS_BUSINESS"})
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


# ---------------------------------------------------------------------------
# GET /admin/summary
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
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR"},
        )
