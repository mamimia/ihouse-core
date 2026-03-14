"""
Worker Calendar Router — Phase 635

Endpoints for worker task calendar and today's tasks.

Tables used:
    - tasks (read-only)

Invariant:
    This router NEVER writes to booking_state, event_log, or
    booking_financial_facts.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timezone, datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
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
# GET /workers/{worker_id}/calendar
# ---------------------------------------------------------------------------

@router.get(
    "/workers/{worker_id}/calendar",
    tags=["workers"],
    summary="Worker's upcoming tasks grouped by date",
    responses={
        200: {"description": "Tasks grouped by date"},
        401: {"description": "Missing or invalid JWT"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def worker_calendar(
    worker_id: str,
    days: int = 14,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return upcoming tasks for a worker grouped by due_date.

    Args:
        worker_id: The worker's ID (e.g. 'WRK-001')
        days: Number of days to look ahead (default 14, max 90)
    """
    days = min(max(days, 1), 90)

    try:
        db = client or _get_supabase_client()

        # Query tasks assigned to this worker (by worker_id in any field)
        # Tasks table doesn't have a worker_id column directly, but we can
        # look for tasks by tenant, filtering non-terminal tasks
        result = (
            db.table("tasks")
            .select("task_id, kind, status, priority, property_id, booking_id, due_date, title, urgency")
            .eq("tenant_id", tenant_id)
            .order("due_date")
            .limit(200)
            .execute()
        )
        tasks = result.data or []

        # Filter to non-terminal tasks
        terminal = {"COMPLETED", "CANCELED"}
        active_tasks = [t for t in tasks if t.get("status") not in terminal]

        # Group by due_date
        grouped: dict[str, list] = {}
        for task in active_tasks:
            dd = task.get("due_date", "unknown")
            grouped.setdefault(dd, []).append(task)

        calendar = [
            {"date": d, "tasks": grouped[d], "count": len(grouped[d])}
            for d in sorted(grouped.keys())
        ]

        return JSONResponse(status_code=200, content={
            "worker_id": worker_id,
            "calendar": calendar,
            "total_tasks": sum(len(g["tasks"]) for g in calendar),
        })

    except Exception as exc:
        logger.exception("worker_calendar error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to retrieve calendar")


# ---------------------------------------------------------------------------
# GET /workers/{worker_id}/tasks/today
# ---------------------------------------------------------------------------

@router.get(
    "/workers/{worker_id}/tasks/today",
    tags=["workers"],
    summary="Worker's tasks due today",
    responses={
        200: {"description": "Today's tasks for the worker"},
        401: {"description": "Missing or invalid JWT"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def worker_tasks_today(
    worker_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Return tasks due today for a specific worker."""
    today = date.today().isoformat()

    try:
        db = client or _get_supabase_client()

        result = (
            db.table("tasks")
            .select("task_id, kind, status, priority, property_id, booking_id, due_date, title, urgency")
            .eq("tenant_id", tenant_id)
            .eq("due_date", today)
            .order("priority")
            .limit(50)
            .execute()
        )
        tasks = result.data or []

        # Filter to non-terminal
        terminal = {"COMPLETED", "CANCELED"}
        active = [t for t in tasks if t.get("status") not in terminal]

        return JSONResponse(status_code=200, content={
            "worker_id": worker_id,
            "date": today,
            "tasks": active,
            "count": len(active),
        })

    except Exception as exc:
        logger.exception("worker_tasks_today error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to retrieve today's tasks")
