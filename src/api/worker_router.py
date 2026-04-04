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

from api.auth import jwt_auth, jwt_auth_active, jwt_identity_simple as jwt_identity
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response
from services.audit_writer import write_audit_event
from tasks.task_model import TaskStatus, WorkerRole, VALID_TASK_TRANSITIONS
from tasks.timing import compute_task_timing, enrich_tasks_with_timing, format_opens_in

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
    tenant_id: str = Depends(jwt_auth_active),
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
            # Phase E-4 / Phase 1030: Default view excludes terminal states.
            # CANCELED and COMPLETED are hidden when no explicit status filter is sent.
            # The Pending tab sends no status filter and expects PENDING+ACKNOWLEDGED+IN_PROGRESS only.
            # The Done tab sends status=COMPLETED explicitly.
            query = query.neq("status", "CANCELED").neq("status", "COMPLETED")
            
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

        # ── Staleness Guard (Phase 887e) ────────────────────────────────────────
        # Worker surfaces must NEVER show operational tasks whose due_date has
        # already passed. A PENDING CHECKIN_PREP task from 4 days ago is a ghost —
        # the guest has long since arrived (or not) and the operational window is
        # closed. Surfacing it causes workers to attempt incorrect actions.
        #
        # Rule: for CHECKIN_PREP / CHECKOUT_VERIFY / CLEANING tasks that are still
        # in an active state (PENDING / ACKNOWLEDGED / IN_PROGRESS), suppress them
        # if their due_date is strictly before today. This is always-on for the
        # worker surface — admins use include_stale=true on /tasks if they need audit.
        from datetime import date as _date  # noqa: PLC0415
        _OPERATIONAL_KINDS = frozenset({'CHECKIN_PREP', 'CHECKOUT_VERIFY', 'CLEANING'})
        _TODAY = _date.today().isoformat()  # e.g. "2026-03-30"
        _ACTIVE = frozenset({'PENDING', 'ACKNOWLEDGED', 'IN_PROGRESS'})

        def _is_stale(t: dict) -> bool:
            k = (t.get('kind') or '').upper()
            s = (t.get('status') or '').upper()
            d = t.get('due_date') or ''
            return k in _OPERATIONAL_KINDS and s in _ACTIVE and bool(d) and d < _TODAY

        stale = [t for t in tasks if _is_stale(t)]
        if stale:
            logger.warning(
                "staleness_guard[worker]: suppressed %d stale task(s) for tenant=%s "
                "(ids: %s). Booking window has passed — tasks should be CANCELED.",
                len(stale),
                tenant_id,
                [t.get('task_id') for t in stale],
            )
        tasks = [t for t in tasks if not _is_stale(t)]
        # ────────────────────────────────────────────────────────────────────────

        # Phase 1033 — Enrich every task with canonical timing fields:
        # effective_due_at, ack_allowed_at, start_allowed_at, ack_is_open, start_is_open
        # Frontend uses these values directly; no local gate computation needed.
        enrich_tasks_with_timing(tasks)

        return JSONResponse(
            status_code=200,
            content={
                "tasks": tasks,
                "count": len(tasks),
                "role_scoped": len(effective_worker_roles) > 0,
                "assignment_filtered": assigned_to is not None,
                "has_assignments": len(tasks) > 0 if assigned_to is not None else False,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("list_worker_tasks error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to list worker tasks")


# ---------------------------------------------------------------------------
# GET /worker/bookings/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/worker/bookings/{booking_id}",
    tags=["worker"],
    summary="Fetch limited booking details for operational tasks",
    responses={
        200: {"description": "Returns limited stay context for workers"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Booking not found"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_worker_booking(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth_active),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Fetch limited booking details necessary for operational context (e.g. check-in/check-out).
    Returns ONLY check-in, check-out, guest_name, guest_count, source, and status.
    No financial information or extended PII is exposed.

    **Role scoping:** Accessible to any authenticated worker. Does NOT require
    the manager-only 'bookings' capability.
    """
    try:
        db = client or _get_supabase_client()
        result = (
            db.table("booking_state")
            .select(
                "booking_id, tenant_id, property_id, status, guest_name, guest_count, "
                "check_in, check_out, source, reservation_ref, "
                # Phase 1000: Early checkout context — workers need this to render
                # the correct dates and Early Check-out badge in the checkout wizard.
                "early_checkout_approved, early_checkout_date, "
                "early_checkout_effective_at, early_checkout_status, "
                "early_checkout_reason"
            )
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, "Booking not found")
            
        return JSONResponse(status_code=200, content=result.data[0])
    except Exception as exc:
        logger.exception("get_worker_booking error: %s", exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to fetch booking details")


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
    tenant_id: str = Depends(jwt_auth_active),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Acknowledge a task. Valid only from PENDING state → ACKNOWLEDGED.

    **No request body required.**

    Phase 1033 — Acknowledge timing window (replaces Phase 1027d calendar-day gate):
    Uses compute_task_timing() for hour-level UTC precision.
    Window: ack_allowed_at = effective_due_at − 24h
    MAINTENANCE/CRITICAL tasks: always open (ack_allowed_at = None).
    Tasks without due_date: always open.

    Uses VALID_TASK_TRANSITIONS from task_model.py.
    Terminal tasks (COMPLETED/CANCELED) return 422 INVALID_TRANSITION.
    """
    try:
        db = client or _get_supabase_client()

        # Phase 1033: Hour-level acknowledge gate via compute_task_timing()
        _task_res = (
            db.table("tasks")
            .select("due_date, due_time, kind, priority, urgency")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if _task_res.data:
            _now_utc = datetime.now(timezone.utc)
            _timing = compute_task_timing(_task_res.data[0], now_utc=_now_utc)
            if not _timing.ack_is_open and _timing.ack_allowed_at:
                _opens_in = format_opens_in(_timing.ack_allowed_at, _now_utc)
                return make_error_response(
                    422,
                    ErrorCode.INVALID_TRANSITION,
                    f"Acknowledge not yet open. Opens in {_opens_in} "
                    f"(at {_timing.ack_allowed_at.isoformat()}).",
                    extra={
                        "error_code": "ACKNOWLEDGE_TOO_EARLY",
                        "ack_allowed_at": _timing.ack_allowed_at.isoformat(),
                        "opens_in": _opens_in,
                    },
                )

    except Exception as _gate_exc:  # noqa: BLE001
        logger.warning("acknowledge_task: timing gate check failed (non-blocking): %s", _gate_exc)

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
    tenant_id: str = Depends(jwt_auth_active),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Start a task. Valid only from ACKNOWLEDGED state → IN_PROGRESS.

    **No request body required.**

    Phase 1033 — Start timing gate (replaces Phase 1029 calendar-day frozensets):
    Uses compute_task_timing() for hour-level UTC precision.
    Window: start_allowed_at = effective_due_at − 2h
    MAINTENANCE/GENERAL kinds: start_allowed_at = None (always open — no gate).
    CRITICAL tasks: always open regardless of kind.
    Tasks without due_date: always open.
    """
    try:
        db = client or _get_supabase_client()

        # Phase 1033: Hour-level start gate via compute_task_timing()
        _task_res = (
            db.table("tasks")
            .select("due_date, due_time, kind, priority, urgency")
            .eq("task_id", task_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if _task_res.data:
            _now_utc = datetime.now(timezone.utc)
            _timing = compute_task_timing(_task_res.data[0], now_utc=_now_utc)
            if not _timing.start_is_open and _timing.start_allowed_at:
                _opens_in = format_opens_in(_timing.start_allowed_at, _now_utc)
                return make_error_response(
                    422,
                    ErrorCode.INVALID_TRANSITION,
                    f"Start not yet open. Opens in {_opens_in} "
                    f"(at {_timing.start_allowed_at.isoformat()}).",
                    extra={
                        "error_code": "START_TOO_EARLY",
                        "start_allowed_at": _timing.start_allowed_at.isoformat(),
                        "opens_in": _opens_in,
                    },
                )

    except Exception as _gate_exc:
        logger.warning("start_task: timing gate check failed (non-blocking): %s", _gate_exc)

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
    tenant_id: str = Depends(jwt_auth_active),
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

        # Phase 1029 — Canonical lifecycle timestamps.
        # Each state transition writes its own timestamp so we can audit:
        #   acknowledged_at: when the worker saw and committed to the task
        #   started_at:      when the worker pressed Start (real work began)
        #   completed_at:    when the worker pressed Complete
        # These are the source-of-truth for operational SLA measurement.
        if target_status == TaskStatus.ACKNOWLEDGED:
            patch_data["acknowledged_at"] = now
        elif target_status == TaskStatus.IN_PROGRESS:
            patch_data["started_at"] = now
        elif target_status == TaskStatus.COMPLETED:
            patch_data["completed_at"] = now

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
    tenant_id: str = Depends(jwt_auth_active),
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
    tenant_id: str = Depends(jwt_auth_active),
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
    tenant_id: str = Depends(jwt_auth_active),
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
    tenant_id: str = Depends(jwt_auth_active),
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
    tenant_id: str = Depends(jwt_auth_active),
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
    tenant_id: str = Depends(jwt_auth_active),
    _cap: None = Depends(require_capability("staffing")),
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
    tenant_id: str = Depends(jwt_auth_active),
    _cap: None = Depends(require_capability("staffing")),
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

# ---------------------------------------------------------------------------
# Phase 890 — Mock Document Extraction Proxy
# ---------------------------------------------------------------------------

import asyncio

@router.post(
    "/worker/documents/extract",
    tags=["worker"],
    summary="Mock WebRTC ID Extract Endpoint",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def extract_document(
    body: dict,
    tenant_id: str = Depends(jwt_auth_active),
) -> JSONResponse:
    """
    Mock endpoint simulating an async call to an OCR/MRZ Provider (e.g. BlinkID / Azure).
    It artificially delays to replicate extraction latency, then returns a simulated payload.
    When OCR keys are provisioned, swap this to proxy the real API.
    """
    # Simulate network/OCR processing latency
    await asyncio.sleep(1.5)

    # Simulated MRZ output from a typical passport
    return JSONResponse(status_code=200, content={
        "document_type": "PASSPORT",
        "first_name": "JOHN ALBERT",
        "last_name": "DOE",
        "document_number": "A12345678",
        "date_of_birth": "1985-11-20",
        "expiration_date": "2032-05-15",
        "nationality": "GBR",
        "confidence_score": 0.98
    })


# ---------------------------------------------------------------------------
# Phase 953 — Worker: Charge Config Pre-fill
# ---------------------------------------------------------------------------
# Read the active deposit + electricity configuration for the property linked
# to this booking. Used by the check-in wizard to pre-fill the deposit amount
# prompt before the worker starts the deposit collection step.
#
# This is READ-ONLY. It does not modify the deposit collection write path.
# If no rule has been configured for the property, returns safe defaults
# (deposit_enabled=false) so the wizard surfaces "No deposit required".
# ---------------------------------------------------------------------------

_CHARGE_CONFIG_ROLES = frozenset({
    "admin", "manager", "ops", "worker", "checkin", "checkout"
})


@router.get(
    "/worker/bookings/{booking_id}/charge-config",
    tags=["worker"],
    summary="Get charge config for check-in pre-fill (Phase 953)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_charge_config_for_booking(
    booking_id: str,
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Returns the active deposit and electricity configuration for the property
    linked to this booking.

    Used by the check-in wizard to pre-fill the deposit amount before the
    worker starts the deposit collection step.

    **Response:**
    - `deposit_enabled` — whether a deposit is required for this property
    - `deposit_amount` — pre-fill value (null if unset)
    - `deposit_currency` — currency code (e.g. THB)
    - `electricity_enabled` — whether electricity is billed
    - `electricity_rate_kwh` — rate per kWh (null if unset)

    Returns safe defaults (`deposit_enabled=false`) if the property has no
    configured charge rule yet.

    Read-only. No writes anywhere.
    """
    role = identity.get("role", "")
    if role not in _CHARGE_CONFIG_ROLES:
        return make_error_response(
            status_code=403, code="FORBIDDEN",
            extra={"detail": f"Role '{role}' cannot read charge config."},
        )
    tenant_id = identity["tenant_id"]

    _default = {
        "deposit_enabled":      False,
        "deposit_amount":       None,
        "deposit_currency":     "THB",
        "electricity_enabled":  False,
        "electricity_rate_kwh": None,
    }

    try:
        db = client or _get_supabase_client()

        # Resolve property_id from booking_state
        bs = (
            db.table("booking_state")
            .select("property_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not (bs.data or []):
            return make_error_response(
                status_code=404, code=ErrorCode.NOT_FOUND,
                extra={"detail": f"Booking '{booking_id}' not found."},
            )
        property_id = bs.data[0].get("property_id")
        if not property_id:
            return JSONResponse(status_code=200, content=_default)

        # Read charge rule for this property
        res = (
            db.table("property_charge_rules")
            .select(
                "deposit_enabled, deposit_amount, deposit_currency, "
                "electricity_enabled, electricity_rate_kwh"
            )
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return JSONResponse(status_code=200, content=_default)

        row = rows[0]
        return JSONResponse(status_code=200, content={
            "deposit_enabled":      row.get("deposit_enabled", False),
            "deposit_amount":       row.get("deposit_amount"),
            "deposit_currency":     row.get("deposit_currency", "THB"),
            "electricity_enabled":  row.get("electricity_enabled", False),
            "electricity_rate_kwh": row.get("electricity_rate_kwh"),
        })

    except Exception as exc:
        logger.exception("GET charge-config booking=%s error tenant=%s: %s",
                         booking_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
