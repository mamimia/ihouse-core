"""
Phase 232 — Pre-Arrival Queue Admin Endpoint

GET /admin/pre-arrival-queue

Returns the current state of the pre-arrival processing queue.
Shows which bookings have been scanned, which tasks were auto-created,
and whether a check-in draft message was generated.

Filters (all optional):
  - date        — filter by check_in date (YYYY-MM-DD)
  - draft_written — 'true' or 'false'
  - limit       — 1–100 (default 50)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


@router.get(
    "/admin/pre-arrival-queue",
    tags=["admin"],
    summary="Pre-arrival processing queue (Phase 232)",
    responses={
        200: {"description": "Queue entries"},
        400: {"description": "Invalid query parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_pre_arrival_queue(
    date: Optional[str] = None,
    draft_written: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return pre-arrival queue entries for this tenant.

    **Query parameters (all optional):**
    - `date`          — filter by check_in date (YYYY-MM-DD)
    - `draft_written` — `true` or `false` — filter by draft status
    - `limit`         — max results (1–100, default 50)

    Ordered by `check_in ASC` (soonest arrivals first).
    """
    if not (1 <= limit <= _MAX_LIMIT):
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"limit must be between 1 and {_MAX_LIMIT}",
        )

    draft_filter: Optional[bool] = None
    if draft_written is not None:
        if draft_written.lower() == "true":
            draft_filter = True
        elif draft_written.lower() == "false":
            draft_filter = False
        else:
            return make_error_response(
                400,
                ErrorCode.VALIDATION_ERROR,
                "draft_written must be 'true' or 'false'",
            )

    try:
        db = client or _get_db()
        query = (
            db.table("pre_arrival_queue")
            .select(
                "id, booking_id, property_id, check_in, tasks_created, "
                "draft_written, draft_preview, scanned_at"
            )
            .eq("tenant_id", tenant_id)
            .order("check_in", desc=False)
            .limit(limit)
        )
        if date is not None:
            query = query.eq("check_in", date)
        if draft_filter is not None:
            query = query.eq("draft_written", draft_filter)

        result = query.execute()
        rows = result.data if result.data else []
        return JSONResponse(
            status_code=200,
            content={"queue": rows, "count": len(rows)},
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("get_pre_arrival_queue error: %s", exc)
        return make_error_response(
            500, ErrorCode.INTERNAL_ERROR, "Failed to query pre-arrival queue"
        )


# ---------------------------------------------------------------------------
# Phase 488 — POST /admin/pre-arrival/scan
# ---------------------------------------------------------------------------

@router.post(
    "/admin/pre-arrival/scan",
    tags=["admin"],
    summary="Trigger pre-arrival scan for upcoming check-ins (Phase 488)",
    responses={
        200: {"description": "Scan results"},
        401: {"description": "Missing or invalid JWT"},
    },
)
async def trigger_pre_arrival_scan(
    lookahead_hours: int = 48,
    dry_run: bool = False,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    POST /admin/pre-arrival/scan?lookahead_hours=48&dry_run=false

    Scans for bookings with check-in within lookahead_hours,
    creates pre_arrival_queue entries and auto-generates tasks.
    """
    try:
        from services.pre_arrival_scanner import run_pre_arrival_scan

        result = run_pre_arrival_scan()

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "tenant_id": tenant_id,
                "lookahead_hours": lookahead_hours,
                **result,
            },
        )
    except Exception as exc:
        logger.exception("POST /admin/pre-arrival/scan error: %s", exc)
        return make_error_response(
            500, ErrorCode.INTERNAL_ERROR, "Pre-arrival scan failed"
        )
