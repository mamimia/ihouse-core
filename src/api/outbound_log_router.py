"""
Phase 145 — Outbound Sync Log Inspector API

Provides read-only visibility into all outbound adapter calls via the
`outbound_sync_log` table written by Phase 144.

Read-only. Never writes. JWT required. Tenant-scoped.

Endpoints:
  GET /admin/outbound-log
      Query params: booking_id, provider, status, limit (default 50, max 200)
      Returns: list of outbound_sync_log rows for this tenant, newest-first.

  GET /admin/outbound-log/{booking_id}
      Returns: all sync log rows for a specific booking (this tenant only).
      404 if no rows found for this booking.

Invariant:
  These endpoints NEVER write to any table.
  They read ONLY from `outbound_sync_log`.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from fastapi import Depends
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_STATUSES = frozenset({"ok", "failed", "dry_run", "skipped"})
_DEFAULT_LIMIT  = 50
_MAX_LIMIT      = 200


# ---------------------------------------------------------------------------
# Supabase client helper (follows admin_router.py pattern)
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _query_log(
    db: Any,
    tenant_id: str,
    booking_id: Optional[str],
    provider: Optional[str],
    status: Optional[str],
    limit: int,
) -> List[dict]:
    """
    Fetch outbound_sync_log rows for this tenant, newest-first.
    Applies optional filters: booking_id, provider, status.
    Returns empty list on any error (best-effort read).
    """
    try:
        q = (
            db.table("outbound_sync_log")
            .select(
                "id, booking_id, tenant_id, provider, external_id, "
                "strategy, status, http_status, message, synced_at"
            )
            .eq("tenant_id", tenant_id)
            .order("synced_at", desc=True)
            .limit(limit)
        )
        if booking_id:
            q = q.eq("booking_id", booking_id)
        if provider:
            q = q.eq("provider", provider)
        if status:
            q = q.eq("status", status)

        result = q.execute()
        return result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_query_log error for tenant=%s booking=%s: %s",
            tenant_id, booking_id, exc,
        )
        return []


# ---------------------------------------------------------------------------
# GET /admin/outbound-log
# ---------------------------------------------------------------------------

@router.get(
    "/admin/outbound-log",
    tags=["admin", "outbound"],
    summary="List outbound sync log entries",
    responses={
        200: {"description": "Outbound sync log entries for this tenant"},
        400: {"description": "Invalid filter parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_outbound_log(
    booking_id: Optional[str] = Query(None, description="Filter by booking_id"),
    provider:   Optional[str] = Query(None, description="Filter by OTA provider"),
    status:     Optional[str] = Query(None, description="Filter by status: ok|failed|dry_run|skipped"),
    limit:      int           = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="Max rows (1-200)"),
    tenant_id:  str           = Depends(jwt_auth),
    client:     Optional[Any] = None,
) -> JSONResponse:
    """
    List outbound sync log entries for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only this tenant's rows are returned.

    **Ordering:** Newest `synced_at` first.

    **Query parameters:**
    - `booking_id` — filter to a specific booking
    - `provider`   — filter to a specific OTA provider (e.g. `airbnb`, `bookingcom`)
    - `status`     — filter by status: `ok`, `failed`, `dry_run`, `skipped`
    - `limit`      — max number of rows to return (default 50, max 200)

    **Source:** `outbound_sync_log` — read-only.
    """
    # Validate optional status filter
    if status and status not in _VALID_STATUSES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"status must be one of: {sorted(_VALID_STATUSES)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()
        rows = _query_log(db, tenant_id, booking_id, provider, status, limit)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "count":     len(rows),
                "limit":     limit,
                "entries":   rows,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/outbound-log error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/outbound-log/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/admin/outbound-log/{booking_id}",
    tags=["admin", "outbound"],
    summary="Get all outbound sync log entries for a booking",
    responses={
        200: {"description": "All outbound sync log entries for this booking"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No sync log entries for this booking"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_outbound_log_for_booking(
    booking_id: str,
    tenant_id:  str           = Depends(jwt_auth),
    client:     Optional[Any] = None,
) -> JSONResponse:
    """
    Get all outbound sync log entries for a specific booking.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Cross-tenant reads return 404 (not 403) to avoid
    leaking booking existence. Same convention as the booking timeline endpoint.

    **Ordering:** Newest `synced_at` first.

    **Source:** `outbound_sync_log` — read-only.

    Returns **404** if no log entries exist yet for this booking.
    """
    try:
        db    = client if client is not None else _get_supabase_client()
        rows  = _query_log(db, tenant_id, booking_id, None, None, _MAX_LIMIT)

        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"booking_id": booking_id},
            )

        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "tenant_id":  tenant_id,
                "count":      len(rows),
                "entries":    rows,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/outbound-log/%s error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
