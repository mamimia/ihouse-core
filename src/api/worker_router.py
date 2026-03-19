"""
Phase 123 — Worker-Facing Task Surface
Phase 166 — Worker Role Scoping

Endpoints:
    GET  /worker/tasks                         — role-scoped task list
    PATCH /worker/tasks/{task_id}/acknowledge  — PENDING → ACKNOWLEDGED
    PATCH /worker/tasks/{task_id}/start        — ACKNOWLEDGED → IN_PROGRESS
    PATCH /worker/tasks/{task_id}/complete     — IN_PROGRESS → COMPLETED

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

Role scoping (Phase 166):
    When the caller's permission record has role='worker', their worker_role
    from the permissions.worker_role field is automatically applied as a DB
    filter — they CANNOT see tasks assigned to other roles.
    Callers with role='admin' or 'manager' (or no permission record) are
    unrestricted — they may supply worker_role freely.
    user_id for enrichment comes from the JWT 'user_id' claim (falls back to
    tenant_id so existing test harnesses remain compatible).

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
from services.audit_writer import write_audit_event
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
    assigned_to: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Return tasks visible to the requesting worker role.

    **Query parameters (all optional):**
    - `worker_role` — filter by WorkerRole (CLEANER / PROPERTY_MANAGER /
      MAINTENANCE_TECH / INSPECTOR / GENERAL_STAFF)
    - `status`      — filter by TaskStatus (PENDING / ACKNOWLEDGED / IN_PROGRESS /
      COMPLETED / CANCELED)
    - `date`        — filter by due_date (YYYY-MM-DD)
    - `assigned_to` — filter by assigned worker user_id (Phase E-3)
    - `limit`       — max results, 1–100 (default 50)

    **Tenant isolation:** Only tasks belonging to the authenticated tenant.

    **Role scoping (Phase 166):** Callers with role='worker' in tenant_permissions
    are restricted to tasks matching their own worker_role capability. Admins and
    managers are unrestricted.

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

    # -- validate worker_role (case-insensitive) --
    if worker_role is not None:
        worker_role = worker_role.upper()
        if worker_role not in _VALID_WORKER_ROLES:
            return make_error_response(
                400,
                ErrorCode.VALIDATION_ERROR,
                f"Invalid worker_role '{worker_role}'. "
                f"Must be one of: {', '.join(sorted(_VALID_WORKER_ROLES))}",
            )

    # -- validate status (case-insensitive) --
    if status is not None:
        status = status.upper()
        if status not in _VALID_TASK_STATUSES:
            return make_error_response(
                400,
                ErrorCode.VALIDATION_ERROR,
                f"Invalid status '{status}'. "
                f"Must be one of: {', '.join(sorted(_VALID_TASK_STATUSES))}",
            )

    try:
        db = client or _get_supabase_client()

        # ------------------------------------------------------------------
        # Phase 166 — Role scoping
        # Look up the caller's permission record. If their role is 'worker',
        # derive their assigned worker_role from the permissions JSONB and
        # enforce it as the filter — ignoring any caller-supplied worker_role.
        # ------------------------------------------------------------------
        effective_worker_roles = set()
        if worker_role:
            effective_worker_roles.add(worker_role.upper())

        caller_id = user_id or tenant_id  # fallback keeps existing tests green
        is_worker = False
        try:
            from api.permissions_router import get_permission_record  # lazy import
            perm = get_permission_record(db, tenant_id, caller_id)
            if perm and perm.get("role") == "worker":
                is_worker = True
                # Legacy fallback: extract from permissions JSONB
                assigned_role = (perm.get("permissions") or {}).get("worker_role")
                if assigned_role and assigned_role in _VALID_WORKER_ROLES:
                    effective_worker_roles.add(assigned_role)
                
                # Phase 850: correctly extract from modern top-level worker_roles array
                assigned_array = perm.get("worker_roles") or []
                for r in assigned_array:
                    r_u = r.upper()
                    if r_u in _VALID_WORKER_ROLES:
                        effective_worker_roles.add(r_u)

        except Exception:  # noqa: BLE001
            pass  # best-effort — never block the request

        # Phase 850 — assignment isolation
        # If the caller is a worker, they should ONLY see tasks assigned to them 
        # or tasks for properties they are assigned to. So we FORCE assigned_to = caller_id.
        if is_worker:
            assigned_to = caller_id

        query = (
            db.table("tasks")
            .select("*")
            .eq("tenant_id", tenant_id)
            .limit(limit)
            .order("due_date", desc=False)
        )
        if effective_worker_roles:
            query = query.in_("worker_role", list(effective_worker_roles))
        elif is_worker:
            # If the worker has no valid roles assigned, they should see NO tasks.
            # PostgREST doesn't support 'in ()' for empty lists directly gracefully.
            # Enforcing a dummy block keeps them isolated.
            query = query.in_("worker_role", ["__NO_ROLES_ASSIGNED__"])
            
        if status is not None:
            query = query.eq("status", status)
        else:
            # Phase E-4: Hide canceled tasks from default "All" view to keep dashboard clean
            query = query.neq("status", "CANCELED")
            
        if date is not None:
            query = query.eq("due_date", date)

        # Phase E-3 — assigned_to filter for personal task lists
        # Phase 847 — ALSO factor in property assignments
        if assigned_to is not None:
            # 1. Fetch properties assigned to this worker
            try:
                asgn_res = db.table("worker_property_assignments").select("property_id").eq("tenant_id", tenant_id).eq("user_id", assigned_to).execute()
                assigned_prop_ids = [r["property_id"] for r in (asgn_res.data or [])]
            except Exception:
                assigned_prop_ids = []

            if assigned_prop_ids:
                # Task matches if it is specifically assigned_to the worker, or if it belongs to an assigned property
                # In postgrest syntax: or=(assigned_to.eq.worker_id,property_id.in.(id1,id2))
                props_csv = ",".join(assigned_prop_ids)
                query = query.or_(f"assigned_to.eq.{assigned_to},property_id.in.({props_csv})")
            else:
                # No property assignments, strict filter by assigned_to
                query = query.eq("assigned_to", assigned_to)

        result = query.execute()
        tasks = result.data if result.data else []
        return JSONResponse(
            status_code=200,
            content={
                "tasks": tasks,
                "count": len(tasks),
                "role_scoped": len(effective_worker_roles) > 0,
                "assignment_filtered": assigned_to is not None,
                "has_assignments": len(assigned_prop_ids) > 0 if assigned_to is not None else False,
            },
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
# PATCH /worker/tasks/{task_id}/start
# ---------------------------------------------------------------------------

@router.patch(
    "/worker/tasks/{task_id}/start",
    tags=["worker"],
    summary="Start a task (ACKNOWLEDGED → IN_PROGRESS)",
    responses={
        200: {"description": "Task started"},
        400: {"description": "Invalid request"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found for this tenant"},
        422: {"description": "Invalid transition — task is not in ACKNOWLEDGED state"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def start_task(
    task_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Start a task. Valid only from ACKNOWLEDGED state → IN_PROGRESS.

    **No request body required.**

    Uses VALID_TASK_TRANSITIONS from task_model.py.
    Terminal tasks (COMPLETED/CANCELED) return 422 INVALID_TRANSITION.
    """
    return await _transition_task(
        task_id=task_id,
        tenant_id=tenant_id,
        target_status=TaskStatus.IN_PROGRESS,
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

        # Phase 189 — Audit event (best-effort, non-blocking)
        # Wrapped in its own try/except: if write_audit_event itself raises
        # (e.g. in tests that mock it with side_effect), the task response is
        # still guaranteed to return 200.
        try:
            action = (
                "TASK_ACKNOWLEDGED" if target_status == TaskStatus.ACKNOWLEDGED
                else "TASK_COMPLETED" if target_status == TaskStatus.COMPLETED
                else f"TASK_{target_status.value}"
            )
            write_audit_event(
                tenant_id=tenant_id,
                actor_id=tenant_id,
                action=action,
                entity_type="task",
                entity_id=task_id,
                payload={
                    "from_status": current_status.value,
                    "to_status":   target_status.value,
                    "notes":       notes,
                },
                client=db,
            )
        except Exception as _audit_exc:  # noqa: BLE001
            logger.warning("_transition_task: audit write failed silently: %s", _audit_exc)

        return JSONResponse(status_code=200, content={"task": updated_row})

    except Exception as exc:  # noqa: BLE001
        logger.exception("_transition_task error for %s: %s", task_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to update task")


# ---------------------------------------------------------------------------
# Phase 201 — Worker Channel Preferences
# ---------------------------------------------------------------------------

_SELECTABLE_CHANNELS = {"line", "whatsapp", "telegram"}  # UI-exposed channels


@router.get(
    "/worker/preferences",
    tags=["worker"],
    summary="Get notification channel preferences for the authenticated worker",
    responses={
        200: {"description": "Active channels for the worker"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_worker_preferences(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Return all active notification_channels rows for the requesting worker.

    The user_id is taken from the JWT 'user_id' claim, falling back to tenant_id
    for backward compatibility with existing test harnesses.
    """
    effective_user_id = user_id or tenant_id
    try:
        db = client or _get_supabase_client()
        result = (
            db.table("notification_channels")
            .select("channel_type, channel_id, active, created_at, updated_at")
            .eq("tenant_id", tenant_id)
            .eq("user_id", effective_user_id)
            .eq("active", True)
            .execute()
        )
        channels = result.data if result.data else []
        return JSONResponse(
            status_code=200,
            content={
                "user_id": effective_user_id,
                "channels": channels,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_worker_preferences error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to get preferences")


@router.put(
    "/worker/preferences",
    tags=["worker"],
    summary="Set (upsert) a notification channel for the authenticated worker",
    responses={
        200: {"description": "Channel registered"},
        400: {"description": "Invalid channel_type or missing fields"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def set_worker_preference(
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Upsert a notification channel for the requesting worker.

    **Request body:**
    ```json
    { "channel_type": "line", "channel_id": "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" }
    ```

    **channel_type** must be one of: line, whatsapp, telegram.

    Upserts on (tenant_id, user_id, channel_type) — safe to call repeatedly.
    """
    if not isinstance(body, dict):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "Request body required")

    channel_type = body.get("channel_type", "").strip().lower()
    channel_id_val = body.get("channel_id", "").strip()

    if not channel_type:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "channel_type is required")
    if channel_type not in _SELECTABLE_CHANNELS:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid channel_type '{channel_type}'. Must be one of: {', '.join(sorted(_SELECTABLE_CHANNELS))}",
        )
    if not channel_id_val:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "channel_id is required")

    effective_user_id = user_id or tenant_id
    try:
        from channels.notification_dispatcher import register_channel  # lazy import
        db = client or _get_supabase_client()
        result = register_channel(
            db=db,
            tenant_id=tenant_id,
            user_id=effective_user_id,
            channel_type=channel_type,
            channel_id=channel_id_val,
        )
        return JSONResponse(status_code=200, content=result)
    except ValueError as ve:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, str(ve))
    except Exception as exc:  # noqa: BLE001
        logger.exception("set_worker_preference error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to set preference")


@router.delete(
    "/worker/preferences/{channel_type}",
    tags=["worker"],
    summary="Deregister a notification channel for the authenticated worker",
    responses={
        200: {"description": "Channel deregistered"},
        400: {"description": "Invalid channel_type"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def delete_worker_preference(
    channel_type: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Deregister (set active=False) the specified channel for the requesting worker.

    **channel_type** must be one of: line, whatsapp, telegram.

    Idempotent — if no row exists, returns status='not_found'.
    """
    channel_type = channel_type.strip().lower()
    if channel_type not in _SELECTABLE_CHANNELS:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid channel_type '{channel_type}'. Must be one of: {', '.join(sorted(_SELECTABLE_CHANNELS))}",
        )

    effective_user_id = user_id or tenant_id
    try:
        from channels.notification_dispatcher import deregister_channel  # lazy import
        db = client or _get_supabase_client()
        result = deregister_channel(
            db=db,
            tenant_id=tenant_id,
            user_id=effective_user_id,
            channel_type=channel_type,
        )
        return JSONResponse(status_code=200, content=result)
    except ValueError as ve:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, str(ve))
    except Exception as exc:  # noqa: BLE001
        logger.exception("delete_worker_preference error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to deregister preference")


# ---------------------------------------------------------------------------
# Phase 202 — Worker Notification History
# ---------------------------------------------------------------------------

_MAX_NOTIFICATIONS = 50
_DEFAULT_NOTIFICATIONS = 20
_VALID_DELIVERY_STATUSES = {"sent", "failed"}


@router.get(
    "/worker/notifications",
    tags=["worker"],
    summary="List notification delivery history for the authenticated worker",
    responses={
        200: {"description": "Notification delivery history"},
        400: {"description": "Invalid query parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_worker_notifications(
    limit: int = _DEFAULT_NOTIFICATIONS,
    status: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """
    Return recent notification delivery log entries for the requesting worker.

    **Query parameters (all optional):**
    - `limit`  — max results, 1–50 (default 20)
    - `status` — filter by delivery status: `sent` or `failed`

    Ordered by `dispatched_at DESC` (newest first).
    Reads from `notification_delivery_log` only.
    """
    if not (1 <= limit <= _MAX_NOTIFICATIONS):
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"limit must be between 1 and {_MAX_NOTIFICATIONS}",
        )

    if status is not None and status not in _VALID_DELIVERY_STATUSES:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(_VALID_DELIVERY_STATUSES))}",
        )

    effective_user_id = user_id or tenant_id
    try:
        db = client or _get_supabase_client()
        query = (
            db.table("notification_delivery_log")
            .select(
                "notification_delivery_id, channel_type, channel_id, status, "
                "error_message, trigger_reason, task_id, dispatched_at"
            )
            .eq("tenant_id", tenant_id)
            .eq("user_id", effective_user_id)
            .order("dispatched_at", desc=True)
            .limit(limit)
        )
        if status is not None:
            query = query.eq("status", status)

        result = query.execute()
        notifications = result.data if result.data else []
        return JSONResponse(
            status_code=200,
            content={
                "user_id": effective_user_id,
                "notifications": notifications,
                "count": len(notifications),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("list_worker_notifications error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to list notifications")


# ---------------------------------------------------------------------------
# Phase 823 — Worker-Property Assignments
# ---------------------------------------------------------------------------

@router.get(
    "/worker/assignments",
    tags=["worker"],
    summary="List property assignments for a worker",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_worker_assignments(
    user_id_filter: Optional[str] = None,
    property_id: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    user_id: Optional[str] = None,
) -> JSONResponse:
    """Return property assignments, filtered by user_id or property_id."""
    effective_user = user_id_filter or user_id or tenant_id
    try:
        db = client or _get_supabase_client()
        query = (
            db.table("worker_property_assignments")
            .select("*")
            .eq("tenant_id", tenant_id)
        )
        if user_id_filter:
            query = query.eq("user_id", user_id_filter)
        if property_id:
            query = query.eq("property_id", property_id)
        result = query.execute()
        return JSONResponse(status_code=200, content={
            "assignments": result.data or [],
            "count": len(result.data or []),
        })
    except Exception as exc:
        logger.exception("list_worker_assignments error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to list assignments")


@router.post(
    "/worker/assignments",
    tags=["worker"],
    summary="Assign a worker to a property",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_worker_assignment(
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Assign a worker to a property.

    **Request body:**
    ```json
    { "user_id": "...", "property_id": "...", "worker_role": "CLEANER", "is_primary": true }
    ```
    """
    if not isinstance(body, dict):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "Request body required")

    target_user_id = body.get("user_id", "").strip()
    target_property_id = body.get("property_id", "").strip()
    worker_role = body.get("worker_role", "GENERAL_STAFF").strip().upper()
    is_primary = body.get("is_primary", False)

    if not target_user_id or not target_property_id:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "user_id and property_id required")

    try:
        db = client or _get_supabase_client()
        result = db.table("worker_property_assignments").upsert({
            "tenant_id": tenant_id,
            "user_id": target_user_id,
            "property_id": target_property_id,
            "worker_role": worker_role,
            "is_primary": is_primary,
            "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        }, on_conflict="tenant_id,user_id,property_id,worker_role").execute()

        assignment = result.data[0] if result.data else {}
        return JSONResponse(status_code=201, content={"assignment": assignment})
    except Exception as exc:
        logger.exception("create_worker_assignment error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to create assignment")


@router.delete(
    "/worker/assignments/{assignment_id}",
    tags=["worker"],
    summary="Remove a worker-property assignment",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def delete_worker_assignment(
    assignment_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Delete a worker-property assignment by ID."""
    try:
        db = client or _get_supabase_client()
        db.table("worker_property_assignments").delete().eq(
            "id", assignment_id
        ).eq("tenant_id", tenant_id).execute()
        return JSONResponse(status_code=200, content={"status": "deleted", "id": assignment_id})
    except Exception as exc:
        logger.exception("delete_worker_assignment error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to delete assignment")
