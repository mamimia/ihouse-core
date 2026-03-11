"""
Phase 253 — Staff Performance Dashboard API

Endpoints:
    GET /admin/staff/performance
        Returns aggregated performance metrics for all workers belonging
        to the tenant. Reads from the `tasks` table.

    GET /admin/staff/performance/{worker_id}
        Returns individual drill-down for a specific worker.

Metrics computed:
    - total_tasks_completed   (count of tasks in state "done")
    - total_tasks_assigned    (count of all tasks assigned to worker)
    - completion_rate         (completed / assigned × 100, %)
    - avg_ack_minutes         (average time from created_at to acknowledged_at)
    - sla_compliance_pct      (% tasks acknowledged within SLA — 5 min for CRITICAL)
    - tasks_per_day           (completed tasks / active days)
    - preferred_channel       (most common notification channel: line / sms / email)

Data source: `tasks` table
    Columns used: worker_id, tenant_id, state, kind, priority,
                  created_at, acknowledged_at, completed_at

Design:
    - JWT auth required
    - Pure aggregation over tasks table — no new tables needed
    - All computations done in Python after fetching rows
    - Optional date range filter: date_from / date_to on created_at
"""
from __future__ import annotations

import logging
import os
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string, return None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _compute_worker_metrics(rows: List[dict]) -> dict:
    """
    Compute performance metrics for a single worker's task rows.
    """
    total = len(rows)
    completed = sum(1 for r in rows if r.get("state") == "done")
    completion_rate = round((completed / total * 100), 1) if total > 0 else 0.0

    # Avg ACK time (minutes)
    ack_deltas: List[float] = []
    sla_met = 0
    sla_applicable = 0

    for r in rows:
        created = _parse_dt(r.get("created_at"))
        acked = _parse_dt(r.get("acknowledged_at"))
        if created and acked:
            delta_min = (acked - created).total_seconds() / 60.0
            ack_deltas.append(delta_min)

            # SLA check: CRITICAL tasks must be ACKed within 5 min
            if r.get("priority") == "critical":
                sla_applicable += 1
                if delta_min <= 5.0:
                    sla_met += 1

    avg_ack = round(sum(ack_deltas) / len(ack_deltas), 1) if ack_deltas else None
    sla_pct = round(sla_met / sla_applicable * 100, 1) if sla_applicable > 0 else 100.0

    # Tasks per day
    dates_active = set()
    for r in rows:
        completed_at = _parse_dt(r.get("completed_at"))
        if completed_at:
            dates_active.add(completed_at.date())
    tasks_per_day = round(completed / len(dates_active), 1) if dates_active else 0.0

    # Preferred channel
    channels = [r.get("notification_channel") for r in rows if r.get("notification_channel")]
    preferred_channel = Counter(channels).most_common(1)[0][0] if channels else None

    # Kind breakdown
    kinds = Counter(r.get("kind", "unknown") for r in rows)

    return {
        "total_tasks_assigned": total,
        "total_tasks_completed": completed,
        "completion_rate": completion_rate,
        "avg_ack_minutes": avg_ack,
        "sla_compliance_pct": sla_pct,
        "tasks_per_day": tasks_per_day,
        "preferred_channel": preferred_channel,
        "kind_breakdown": dict(kinds),
    }


# ---------------------------------------------------------------------------
# GET /admin/staff/performance
# ---------------------------------------------------------------------------

@router.get(
    "/admin/staff/performance",
    tags=["admin"],
    summary="Aggregated staff performance metrics",
    responses={
        200: {"description": "Staff performance data"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_staff_performance(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns performance metrics for all workers.

    **Optional filters:** `date_from`, `date_to` (ISO date, filters on created_at).

    **Authentication:** Bearer JWT. `sub` = `tenant_id`.
    """
    try:
        db = _client if _client is not None else _get_supabase_client()

        q = (
            db.table("tasks")
            .select(
                "worker_id, state, kind, priority, created_at, "
                "acknowledged_at, completed_at, notification_channel"
            )
            .eq("tenant_id", tenant_id)
        )
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to)

        result = q.execute()
        rows: List[dict] = result.data or []

        # Group by worker_id
        workers: Dict[str, List[dict]] = {}
        for r in rows:
            wid = r.get("worker_id") or "unassigned"
            workers.setdefault(wid, []).append(r)

        staff = []
        for wid, w_rows in sorted(workers.items()):
            metrics = _compute_worker_metrics(w_rows)
            staff.append({"worker_id": wid, **metrics})

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "total_workers": len(staff),
                "total_tasks": len(rows),
                "filters": {"date_from": date_from, "date_to": date_to},
                "staff": staff,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/staff/performance error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/staff/performance/{worker_id}
# ---------------------------------------------------------------------------

@router.get(
    "/admin/staff/performance/{worker_id}",
    tags=["admin"],
    summary="Individual worker performance drill-down",
    responses={
        200: {"description": "Worker performance data"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Worker has no tasks"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_worker_performance(
    worker_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns detailed performance for a specific worker.

    **Authentication:** Bearer JWT. `sub` = `tenant_id`.
    """
    try:
        db = _client if _client is not None else _get_supabase_client()

        q = (
            db.table("tasks")
            .select(
                "worker_id, state, kind, priority, created_at, "
                "acknowledged_at, completed_at, notification_channel"
            )
            .eq("tenant_id", tenant_id)
            .eq("worker_id", worker_id)
        )
        if date_from:
            q = q.gte("created_at", date_from)
        if date_to:
            q = q.lte("created_at", date_to)

        result = q.execute()
        rows: List[dict] = result.data or []

        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"No tasks found for worker {worker_id!r}.",
            )

        metrics = _compute_worker_metrics(rows)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "worker_id": worker_id,
                "filters": {"date_from": date_from, "date_to": date_to},
                **metrics,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/staff/performance/%s error: %s", worker_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
