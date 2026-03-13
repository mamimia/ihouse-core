"""
Phase 248 — Maintenance & Housekeeping Task Templates

Endpoints:
    GET    /admin/task-templates
        List all task templates (tenant-scoped), with optional filter by
        kind, trigger_event, and active status.

    POST   /admin/task-templates
        Create a new task template.
        Body: { title, kind, priority (optional), estimated_minutes (optional),
                trigger_event (optional), instructions (optional) }
        Upsert semantics: if a template with the same title already exists
        for this tenant, update its fields.

    DELETE /admin/task-templates/{template_id}
        Soft-delete (set active=False) a task template.
        Hard-delete is not supported — templates should be deactivated.

Invariants:
    - All endpoints require JWT auth (tenant_id from sub claim).
    - Reads/writes to task_templates table only.
    - Valid priorities: critical, high, normal (default), low.
    - estimated_minutes must be > 0 if provided.
    - Soft-delete: DELETE sets active=False, does not remove the row.
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

_VALID_PRIORITIES = {"critical", "high", "normal", "low"}


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /admin/task-templates
# ---------------------------------------------------------------------------

@router.get(
    "/admin/task-templates",
    tags=["admin"],
    summary="List task templates for the tenant",
    responses={
        200: {"description": "List of task templates"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_task_templates(
    kind: Optional[str] = None,
    trigger_event: Optional[str] = None,
    active_only: bool = True,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    List task templates.

    **Query parameters:**
    - `kind` *(optional)* — filter by task kind (e.g. "housekeeping")
    - `trigger_event` *(optional)* — filter by trigger (e.g. "BOOKING_CREATED")
    - `active_only` *(default true)* — include only active templates

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    try:
        db = _client if _client is not None else _get_supabase_client()
        q = (
            db.table("task_templates")
            .select(
                "id, title, kind, priority, estimated_minutes, "
                "trigger_event, instructions, active, created_at, updated_at"
            )
            .eq("tenant_id", tenant_id)
        )
        if active_only:
            q = q.eq("active", True)
        if kind:
            q = q.eq("kind", kind)
        if trigger_event:
            q = q.eq("trigger_event", trigger_event)

        result = q.order("title").execute()
        templates = result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "count": len(templates),
                "filters": {
                    "kind": kind,
                    "trigger_event": trigger_event,
                    "active_only": active_only,
                },
                "templates": templates,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/task-templates error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /admin/task-templates
# ---------------------------------------------------------------------------

@router.post(
    "/admin/task-templates",
    tags=["admin"],
    summary="Create or update a task template",
    status_code=201,
    responses={
        201: {"description": "Template created or updated"},
        400: {"description": "Validation error"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_task_template(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Create or update a task template.

    **Body (JSON):**
    - `title` *(required)* — unique name for this template within the tenant
    - `kind` *(required)* — task kind (e.g. "housekeeping", "maintenance", "inspection")
    - `priority` *(optional, default "normal")* — critical | high | normal | low
    - `estimated_minutes` *(optional)* — positive integer
    - `trigger_event` *(optional)* — event that auto-spawns the task
    - `instructions` *(optional)* — step-by-step text for the worker

    **Upsert:** if a template with the same `title` already exists for this tenant,
    all other fields are updated.

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    title = body.get("title")
    kind = body.get("kind")

    if not title or not kind:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="title and kind are required.",
        )

    priority = body.get("priority", "normal")
    if priority not in _VALID_PRIORITIES:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"priority must be one of: {', '.join(sorted(_VALID_PRIORITIES))}.",
        )

    estimated_minutes = body.get("estimated_minutes")
    if estimated_minutes is not None:
        try:
            estimated_minutes = int(estimated_minutes)
            if estimated_minutes <= 0:
                raise ValueError()
        except (TypeError, ValueError):
            return make_error_response(
                status_code=400,
                code="VALIDATION_ERROR",
                message="estimated_minutes must be a positive integer.",
            )

    try:
        db = _client if _client is not None else _get_supabase_client()
        row = {
            "tenant_id": tenant_id,
            "title": title,
            "kind": kind,
            "priority": priority,
            "estimated_minutes": estimated_minutes,
            "trigger_event": body.get("trigger_event"),
            "instructions": body.get("instructions"),
            "active": True,
        }
        result = (
            db.table("task_templates")
            .upsert(row, on_conflict="tenant_id,title")
            .execute()
        )
        saved = result.data[0] if result.data else row

        return JSONResponse(
            status_code=201,
            content={
                "tenant_id": tenant_id,
                "template": saved,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/task-templates error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# DELETE /admin/task-templates/{template_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/admin/task-templates/{template_id}",
    tags=["admin"],
    summary="Soft-delete a task template (sets active=False)",
    responses={
        200: {"description": "Template deactivated"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Template not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def deactivate_task_template(
    template_id: str,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Soft-delete a task template by setting `active=False`.

    The template is not removed from the database; it will no longer appear
    in active-only list queries and will not be used to auto-spawn tasks.

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    try:
        db = _client if _client is not None else _get_supabase_client()

        # Verify it exists and belongs to this tenant
        chk = (
            db.table("task_templates")
            .select("id, active")
            .eq("id", template_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = chk.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"Template {template_id!r} not found.",
            )

        # Soft-delete
        db.table("task_templates").update({"active": False}).eq(
            "id", template_id
        ).eq("tenant_id", tenant_id).execute()

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "template_id": template_id,
                "active": False,
                "message": "Template deactivated.",
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("DELETE /admin/task-templates/%s error: %s", template_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 489 — POST /admin/task-templates/seed
# ---------------------------------------------------------------------------

@router.post(
    "/admin/task-templates/seed",
    tags=["admin"],
    summary="Seed default task templates for this tenant (Phase 489)",
    responses={
        200: {"description": "Seed results"},
        401: {"description": "Missing or invalid JWT"},
    },
)
async def seed_task_templates(
    dry_run: bool = False,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /admin/task-templates/seed?dry_run=false

    Seeds 6 default operational task templates (Cleaning, Pre-Arrival,
    Guest Welcome, Maintenance, VIP Setup, Linen Rotation).
    Idempotent — skips kinds that already exist.
    """
    try:
        from services.task_template_seeder import seed_default_templates
        db = _client if _client is not None else _get_supabase_client()

        result = seed_default_templates(
            tenant_id=tenant_id,
            dry_run=dry_run,
            db=db,
        )

        return JSONResponse(
            status_code=200,
            content={
                "status": "ok",
                "tenant_id": tenant_id,
                **result,
            },
        )
    except Exception as exc:
        logger.exception("POST /admin/task-templates/seed error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
