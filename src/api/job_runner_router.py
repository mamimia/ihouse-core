"""
Phase 516 — Job Runner Management API Router

Exposes the job_runner.py service (Phase 495) via HTTP endpoints.

Endpoints:
    GET  /admin/jobs/status   — List all registered jobs and their last run status
    POST /admin/jobs/trigger  — Trigger job execution (optional: specific jobs, dry-run)
    GET  /admin/jobs/history  — View recent job execution history
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["job-runner"])


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


class TriggerJobsRequest(BaseModel):
    jobs: Optional[List[str]] = Field(default=None, description="Specific jobs to trigger (null = all due)")
    force: bool = Field(default=False, description="Force run regardless of interval")
    dry_run: bool = Field(default=True, description="Report which jobs would run without executing")


@router.get(
    "/admin/jobs/status",
    tags=["job-runner"],
    summary="List all registered scheduled jobs (Phase 516)",
    responses={200: {"description": "Job definitions and status."}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_jobs_status(
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    from services.job_runner import JOBS
    jobs = {
        name: {
            "description": defn["description"],
            "interval_hours": defn["interval_hours"],
        }
        for name, defn in JOBS.items()
    }
    return JSONResponse(status_code=200, content={
        "total_jobs": len(jobs),
        "jobs": jobs,
    })


@router.post(
    "/admin/jobs/trigger",
    tags=["job-runner"],
    summary="Trigger scheduled job execution (Phase 516)",
    responses={
        200: {"description": "Job execution results."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def trigger_jobs(
    body: TriggerJobsRequest,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    try:
        from services.job_runner import run_all_due_jobs
        result = run_all_due_jobs(
            force=body.force,
            dry_run=body.dry_run,
            jobs_filter=body.jobs,
        )
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/jobs/trigger error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/admin/jobs/history",
    tags=["job-runner"],
    summary="View recent job execution history (Phase 516)",
    responses={
        200: {"description": "Job history entries."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_jobs_history(
    limit: int = Query(default=50, ge=1, le=200, description="Max entries"),
    job_name: Optional[str] = Query(default=None, description="Filter by job name"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        query = (
            db.table("scheduled_job_log")
            .select("*")
            .order("started_at", desc=True)
            .limit(limit)
        )
        if job_name:
            query = query.eq("job_name", job_name)
        result = query.execute()
        return JSONResponse(status_code=200, content={
            "total": len(result.data or []),
            "entries": result.data or [],
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/jobs/history error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
