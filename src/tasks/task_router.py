"""
Task Query and Transition API — Phase 113

Endpoints:
    GET  /tasks                   — list tasks for tenant, with filters
    GET  /tasks/{task_id}         — get single task by task_id
    PATCH /tasks/{task_id}/status — transition task status (ack/start/done/cancel)

Filters for GET /tasks:
    property_id   - filter by property (optional)
    booking_id    - filter by booking (optional, Phase 158)
    status        - filter by TaskStatus value (optional, all statuses allowed)
    kind          - filter by TaskKind (optional)
    due_date      - filter by due_date (YYYY-MM-DD, optional)
    limit         - max results, 1–100, default 50

Rules:
    - JWT auth required on all endpoints.
    - Tenant isolation enforced at DB level (.eq("tenant_id", tenant_id)).
    - GET endpoints are strictly read-only.
    - PATCH /status enforces valid transition rules (VALID_TASK_TRANSITIONS).
    - Invalid transitions return 422 INVALID_TRANSITION.

Supabase table: `tasks`
    Required columns: task_id, tenant_id, kind, status, priority, urgency,
                      worker_role, ack_sla_minutes, booking_id, property_id,
                      due_date, title, description, created_at, updated_at,
                      notes, canceled_reason

Invariant (Phase 113):
    This router NEVER writes to booking_state, event_log, or booking_financial_facts.
    PATCH /status writes ONLY to the `tasks` table.
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
from tasks.task_model import TaskKind, TaskStatus, VALID_TASK_TRANSITIONS

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50
_VALID_TASK_STATUSES = {s.value for s in TaskStatus}
_VALID_TASK_KINDS = {k.value for k in TaskKind}


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /tasks
# ---------------------------------------------------------------------------

@router.get(
    "/tasks",
    tags=["tasks"],
    summary="List tasks for tenant with optional filters",
    responses={
        200: {"description": "Array of task objects (zero or more)"},
        400: {"description": "Invalid query parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_tasks(
    property_id: Optional[str] = None,
    booking_id: Optional[str] = None,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    due_date: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return tasks for the authenticated tenant.

    **Filters (all optional):**
    - `property_id` — filter by property
    - `status`      — filter by TaskStatus (PENDING / ACKNOWLEDGED / IN_PROGRESS /
                      COMPLETED / CANCELED)
    - `kind`        — filter by TaskKind (CLEANING / CHECKIN_PREP / CHECKOUT_VERIFY /
                      MAINTENANCE / GENERAL)
    - `due_date`    — filter by due_date (YYYY-MM-DD)
    - `limit`       — max results, 1–100 (default 50)
    """
    # --- validate limit ---
    if not (1 <= limit <= _MAX_LIMIT):
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"limit must be between 1 and {_MAX_LIMIT}",
        )

    # --- validate status ---
    if status is not None and status not in _VALID_TASK_STATUSES:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(_VALID_TASK_STATUSES))}",
        )

    # --- validate kind ---
    if kind is not None and kind not in _VALID_TASK_KINDS:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid kind '{kind}'. Must be one of: {', '.join(sorted(_VALID_TASK_KINDS))}",
        )

    # --- query ---
    try:
        db = client or _get_supabase_client()
        query = (
            db.table("tasks")
            .select("*")
            .eq("tenant_id", tenant_id)
            .limit(limit)
            .order("created_at", desc=True)
        )
        if property_id is not None:
            query = query.eq("property_id", property_id)
        if booking_id is not None:
            query = query.eq("booking_id", booking_id)
        if status is not None:
            query = query.eq("status", status)
        if kind is not None:
            query = query.eq("kind", kind)
        if due_date is not None:
            query = query.eq("due_date", due_date)

        result = query.execute()
        tasks = result.data if result.data else []
        return JSONResponse(status_code=200, content={"tasks": tasks, "count": len(tasks)})

    except Exception as exc:  # noqa: BLE001
        logger.exception("list_tasks error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to list tasks")


# ---------------------------------------------------------------------------
# GET /tasks/{task_id}
# ---------------------------------------------------------------------------

@router.get(
    "/tasks/{task_id}",
    tags=["tasks"],
    summary="Get a single task by task_id",
    responses={
        200: {"description": "Task object"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found for this tenant"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_task(
    task_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return a single task by `task_id`.

    **Tenant isolation:** Only tasks belonging to the authenticated tenant are
    returned. Cross-tenant reads return 404 (not 403) to avoid leaking
    task existence.
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
        return JSONResponse(status_code=200, content={"task": result.data[0]})

    except Exception as exc:  # noqa: BLE001
        logger.exception("get_task error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to retrieve task")


# ---------------------------------------------------------------------------
# PATCH /tasks/{task_id}/status
# ---------------------------------------------------------------------------

@router.patch(
    "/tasks/{task_id}/status",
    tags=["tasks"],
    summary="Transition a task to a new status",
    responses={
        200: {"description": "Task updated with new status"},
        400: {"description": "Missing or invalid request body"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task not found for this tenant"},
        422: {"description": "Invalid status transition"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def patch_task_status(
    task_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Transition a task to a new status.

    **Request body:**
    ```json
    {
      "status": "ACKNOWLEDGED",
      "canceled_reason": "optional — defaults to 'Canceled via API' when status=CANCELED"
    }
    ```

    **Valid transitions:**
    ```
    PENDING → ACKNOWLEDGED | CANCELED
    ACKNOWLEDGED → IN_PROGRESS | CANCELED
    IN_PROGRESS → COMPLETED | CANCELED
    COMPLETED → (none — terminal)
    CANCELED → (none — terminal)
    ```
    """
    # --- validate body has status ---
    new_status_str = body.get("status") if isinstance(body, dict) else None
    if not new_status_str:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR, "Request body must include 'status'"
        )

    if new_status_str not in _VALID_TASK_STATUSES:
        return make_error_response(
            400,
            ErrorCode.VALIDATION_ERROR,
            f"Invalid status '{new_status_str}'. Must be one of: {', '.join(sorted(_VALID_TASK_STATUSES))}",
        )

    new_status = TaskStatus(new_status_str)
    canceled_reason: Optional[str] = body.get("canceled_reason") if isinstance(body, dict) else None
    if new_status == TaskStatus.CANCELED and not canceled_reason:
        canceled_reason = "Canceled via API"

    try:
        db = client or _get_supabase_client()

        # --- fetch current task ---
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

        current_row = result.data[0]
        current_status = TaskStatus(current_row["status"])

        # --- validate transition ---
        allowed = VALID_TASK_TRANSITIONS.get(current_status, frozenset())
        if new_status not in allowed:
            allowed_str = ", ".join(s.value for s in allowed) or "none (terminal state)"
            return make_error_response(
                422,
                ErrorCode.INVALID_TRANSITION,
                f"Cannot transition from {current_status.value} to {new_status.value}. "
                f"Allowed: {allowed_str}",
            )

        # --- apply update ---
        now = datetime.now(tz=timezone.utc).isoformat()
        patch_data: dict = {"status": new_status.value, "updated_at": now}
        if new_status == TaskStatus.CANCELED:
            patch_data["canceled_reason"] = canceled_reason

        update_result = (
            db.table("tasks")
            .update(patch_data)
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )

        updated_row = update_result.data[0] if update_result.data else {**current_row, **patch_data}
        return JSONResponse(status_code=200, content={"task": updated_row})

    except Exception as exc:  # noqa: BLE001
        logger.exception("patch_task_status error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to update task status")


# ---------------------------------------------------------------------------
# Phase 633 — GET /tasks/{task_id}/navigate
# ---------------------------------------------------------------------------

@router.get(
    "/tasks/{task_id}/navigate",
    tags=["tasks"],
    summary="Get GPS navigation info for a task's property (Phase 633)",
    responses={
        200: {"description": "GPS coordinates and map URL"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Task or property not found"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def navigate_to_property(
    task_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return GPS coordinates and Google Maps URL for the property linked to this task.
    Used by field workers to navigate to the property.
    """
    try:
        db = client or _get_supabase_client()

        # Look up the task
        task_result = (
            db.table("tasks")
            .select("property_id, title")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not task_result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"Task '{task_id}' not found")

        property_id = task_result.data[0].get("property_id", "")

        # Look up property GPS
        prop_result = (
            db.table("properties")
            .select("latitude, longitude, display_name")
            .eq("property_id", property_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not prop_result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"Property '{property_id}' not found")

        prop = prop_result.data[0]
        lat = prop.get("latitude")
        lng = prop.get("longitude")

        if lat is None or lng is None:
            return JSONResponse(status_code=200, content={
                "task_id": task_id,
                "property_id": property_id,
                "property_name": prop.get("display_name", ""),
                "has_gps": False,
                "message": "No GPS coordinates saved for this property",
            })

        map_url = f"https://maps.google.com/?q={lat},{lng}"
        return JSONResponse(status_code=200, content={
            "task_id": task_id,
            "property_id": property_id,
            "property_name": prop.get("display_name", ""),
            "has_gps": True,
            "latitude": lat,
            "longitude": lng,
            "map_url": map_url,
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception("navigate_to_property error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to get navigation info")


# ---------------------------------------------------------------------------
# Phase 206 — POST /tasks/pre-arrival/{booking_id}
# ---------------------------------------------------------------------------

@router.post(
    "/tasks/pre-arrival/{booking_id}",
    tags=["tasks"],
    summary="Generate pre-arrival guest tasks for a booking (Phase 206)",
    description=(
        "Generate GUEST_WELCOME + CHECKIN_PREP tasks enriched with the guest "
        "profile linked to this booking.\n\n"
        "**Flow:** Looks up `booking_state` for property_id + check_in, resolves"
        " linked guest via `booking_guest_link`, calls `tasks_for_pre_arrival()`, "
        "upserts tasks via `task_writer`.\n\n"
        "**No guest linked?** Falls back to name `'Guest'` — tasks are still created.\n\n"
        "**Idempotent:** Same inputs → same deterministic task_ids → upsert is safe to call again."
    ),
    responses={
        200: {"description": "Pre-arrival tasks created/upserted."},
        401: {"description": "Missing or invalid JWT."},
        404: {"description": "Booking not found for this tenant."},
        500: {"description": "Unexpected internal error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def trigger_pre_arrival_tasks(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /tasks/pre-arrival/{booking_id}

    Look up booking + optional guest. Emit and upsert pre-arrival tasks.
    JWT auth required (tenant isolation).
    """
    try:
        db = client or _get_supabase_client()

        # --- Step 1: Resolve booking ---
        booking_result = (
            db.table("booking_state")
            .select("booking_id, property_id, check_in, tenant_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not booking_result.data:
            return make_error_response(
                404, ErrorCode.NOT_FOUND,
                f"Booking '{booking_id}' not found for this tenant",
            )

        booking = booking_result.data[0]
        property_id: str = booking.get("property_id") or ""
        check_in: str = booking.get("check_in") or ""

        # --- Step 2: Resolve guest (optional) ---
        guest_name: Optional[str] = None
        special_requests: Optional[str] = None

        try:
            link_result = (
                db.table("booking_guest_link")
                .select("guest_id")
                .eq("booking_id", booking_id)
                .limit(1)
                .execute()
            )
            if link_result.data and link_result.data[0].get("guest_id"):
                guest_id = link_result.data[0]["guest_id"]
                guest_result = (
                    db.table("guests")
                    .select("first_name, special_requests")
                    .eq("guest_id", guest_id)
                    .eq("tenant_id", tenant_id)
                    .limit(1)
                    .execute()
                )
                if guest_result.data:
                    g = guest_result.data[0]
                    guest_name = g.get("first_name")
                    special_requests = g.get("special_requests")
        except Exception:  # noqa: BLE001
            # Guest lookup is best-effort — proceed without guest data
            logger.warning("pre_arrival: guest lookup failed for booking %s — using fallback", booking_id)

        # --- Step 3: Generate tasks ---
        from tasks.pre_arrival_tasks import tasks_for_pre_arrival  # noqa: PLC0415
        now = datetime.now(tz=timezone.utc).isoformat()
        tasks = tasks_for_pre_arrival(
            tenant_id=tenant_id,
            booking_id=booking_id,
            property_id=property_id,
            check_in=check_in,
            guest_name=guest_name,
            special_requests=special_requests,
            created_at=now,
        )

        # --- Step 4: Upsert tasks ---
        from tasks.task_writer import _task_to_row  # noqa: PLC0415
        rows = [_task_to_row(t) for t in tasks]
        try:
            db.table("tasks").upsert(rows, on_conflict="task_id").execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("pre_arrival: task upsert failed for booking %s: %s", booking_id, exc)

        tasks_created = [
            {
                "task_id": t.task_id,
                "kind": t.kind.value,
                "title": t.title,
                "priority": t.priority.value,
                "due_date": t.due_date,
            }
            for t in tasks
        ]

        resolved_name = guest_name.strip() if guest_name and guest_name.strip() else "Guest"
        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "guest_name": resolved_name,
                "tasks_created": tasks_created,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("trigger_pre_arrival_tasks error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to generate pre-arrival tasks")

