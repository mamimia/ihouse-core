"""
Phase 123 — Worker-Facing Task Surface

Endpoints:
    GET  /worker/tasks                         — role-scoped task list
    PATCH /worker/tasks/{task_id}/acknowledge  — PENDING → ACKNOWLEDGED
    PATCH /worker/tasks/{task_id}/complete     — ACKNOWLEDGED|IN_PROGRESS → COMPLETED

Rules:
    - JWT auth required on all endpoints.
    - Tenant isolation enforced at DB level (.eq("tenant_id", tenant_id)).
    - worker_role filter applied at DB level when provided.
    - acknowledge: enforces PENDING → ACKNOWLEDGED transition only.
    - complete: enforces ACKNOWLEDGED|IN_PROGRESS → COMPLETED transition only.
    - Both PATCH endpoints use VALID_TASK_TRANSITIONS from task_model.py.
    - Notes appended on complete (if provided in body) — stored in `notes` column.
    - Terminal tasks (COMPLETED/CANCELED) → 422 INVALID_TRANSITION on
      acknowledge/complete attempts.

Invariant (Phase 123):
    This router NEVER writes to booking_state, event_log, or booking_financial_facts.
    All writes target the `tasks` table exclusively.
    External channels (LINE/WhatsApp) are NOT wired — in-app only (Phase 124+).
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
from tasks.task_model import TaskStatus, WorkerRole, VALID_TASK_TRANSITIONS

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50
_VALID_WORKER_ROLES = {r.value for r in WorkerRole}
_VALID_TASK_STATUSES = {s.value for s in TaskStatus}


# ---------------------------------------------------------------------------
# Supabase client factory (patchable in tests)
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    """Return a Supabase client. Patched in tests."""
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /worker/tasks
# ---------------------------------------------------------------------------

@router.get(
    "/worker/tasks",
    tags=["worker"],
    summary="List tasks for a given worker role",
    responses={
        200: {"description": "Array of task objects"},
        400: {"description": "Invalid query parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_worker_tasks(
    worker_role: Optional[str] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return tasks visible to the requesting worker role.

    **Query parameters (all optional):**
    - `worker_role` — filter by WorkerRole (CLEANER / PROPERTY_MANAGER /
      MAINTENANCE_TECH / INSPECTOR / GENERAL_STAFF)
    - `status`      — filter by TaskStatus (PENDING / ACKNOWLEDGED / IN_PROGRESS /
      COMPLETED / CANCELED)
    - `date`        — filter by due_date (YYYY-MM-DD)
    - `limit`       — max results, 1–100 (default 50)

    **Tenant isolation:** Only tasks belonging to the authenticated tenant.

    **Source:** Reads from `tasks` table only. Never reads `booking_financial_facts`
    or `booking_state`.
    """
    # -- validate limit --
    if not (1 <= limit <= _MAX_LIMIT):
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"limit must be between 1 and {_MAX_LIMIT}",
        )

    # -- validate worker_role --
    if worker_role is not None and worker_role not in _VALID_WORKER_ROLES:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid worker_role '{worker_role}'. "
            f"Must be one of: {', '.join(sorted(_VALID_WORKER_ROLES))}",
        )

    # -- validate status --
    if status is not None and status not in _VALID_TASK_STATUSES:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid status '{status}'. "
            f"Must be one of: {', '.join(sorted(_VALID_TASK_STATUSES))}",
        )

    try:
        db = client or _get_supabase_client()
        query = (
            db.table("tasks")
            .select("*")
            .eq("tenant_id", tenant_id)
            .limit(limit)
            .order("due_date", desc=False)
        )
        if worker_role is not None:
            query = query.eq("worker_role", worker_role)
        if status is not None:
            query = query.eq("status", status)
        if date is not None:
            query = query.eq("due_date", date)

        result = query.execute()
        tasks = result.data if result.data else []
        return JSONResponse(
            status_code=200,
            content={"tasks": tasks, "count": len(tasks)},
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("list_worker_tasks error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to list worker tasks")


# ---------------------------------------------------------------------------
# PATCH /worker/tasks/{task_id}/acknowledge
# ---------------------------------------------------------------------------

@router.patch(
    "/worker/tasks/{task_id}/acknowledge",
    tags=["worker"],
    summary="Acknowledge a task (PENDING → ACKNOWLEDGED)",
    responses={
        200: {"description": "Task acknowledged"},
        400: {"description": "Invalid request"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found for this tenant"},
        422: {"description": "Invalid transition — task is not in PENDING state"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def acknowledge_task(
    task_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Acknowledge a task. Valid only from PENDING state → ACKNOWLEDGED.

    **No request body required.**

    Uses VALID_TASK_TRANSITIONS from task_model.py.
    Terminal tasks (COMPLETED/CANCELED) return 422 INVALID_TRANSITION.
    """
    return await _transition_task(
        task_id=task_id,
        tenant_id=tenant_id,
        target_status=TaskStatus.ACKNOWLEDGED,
        client=client,
    )


# ---------------------------------------------------------------------------
# PATCH /worker/tasks/{task_id}/complete
# ---------------------------------------------------------------------------

@router.patch(
    "/worker/tasks/{task_id}/complete",
    tags=["worker"],
    summary="Mark a task as complete (ACKNOWLEDGED|IN_PROGRESS → COMPLETED)",
    responses={
        200: {"description": "Task completed"},
        400: {"description": "Invalid request"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found for this tenant"},
        422: {"description": "Invalid transition — task is not in an completable state"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def complete_task(
    task_id: str,
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Complete a task. Valid from ACKNOWLEDGED or IN_PROGRESS → COMPLETED.

    **Optional request body:**
    ```json
    { "notes": "Task completed — property cleaned and inspected" }
    ```

    Uses VALID_TASK_TRANSITIONS from task_model.py.
    Terminal tasks (COMPLETED/CANCELED) return 422 INVALID_TRANSITION.
    """
    notes: Optional[str] = None
    if isinstance(body, dict):
        notes = body.get("notes")

    return await _transition_task(
        task_id=task_id,
        tenant_id=tenant_id,
        target_status=TaskStatus.COMPLETED,
        client=client,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Shared transition helper
# ---------------------------------------------------------------------------

async def _transition_task(
    task_id: str,
    tenant_id: str,
    target_status: TaskStatus,
    client: Optional[Any],
    notes: Optional[str] = None,
) -> JSONResponse:
    """
    Fetch → validate transition → update.
    Shared by acknowledge and complete endpoints.
    """
    try:
        db = client or _get_supabase_client()

        result = (
            db.table("tasks")
            .select("*")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"Task '{task_id}' not found")

        row = result.data[0]
        current_status = TaskStatus(row["status"])

        allowed = VALID_TASK_TRANSITIONS.get(current_status, frozenset())
        if target_status not in allowed:
            allowed_str = ", ".join(s.value for s in allowed) or "none (terminal state)"
            return make_error_response(
                422,
                ErrorCode.INVALID_TRANSITION,
                f"Cannot transition from {current_status.value} to {target_status.value}. "
                f"Allowed: {allowed_str}",
            )

        now = datetime.now(tz=timezone.utc).isoformat()
        patch_data: dict = {"status": target_status.value, "updated_at": now}

        if notes:
            # Append to existing notes list (stored as JSONB or text[]  in DB).
            # We treat notes as a single string appended to `notes` field if it exists.
            existing_notes = row.get("notes") or []
            if isinstance(existing_notes, list):
                patch_data["notes"] = existing_notes + [notes]
            else:
                patch_data["notes"] = [notes]

        update_result = (
            db.table("tasks")
            .update(patch_data)
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )

        updated_row = update_result.data[0] if update_result.data else {**row, **patch_data}
        return JSONResponse(status_code=200, content={"task": updated_row})

    except Exception as exc:  # noqa: BLE001
        logger.exception("_transition_task error for %s: %s", task_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to update task")
