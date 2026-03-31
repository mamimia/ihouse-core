"""
Phase 189 — Audit Events Query API

GET /admin/audit

Returns a paginated, ordered list of audit events for investigation and
the Manager UI activity feed. Supports optional filtering by entity_type,
entity_id, and actor_id.

Design rules:
- JWT auth required. Tenant-isolated at DB level.
- Read-only endpoint: SELECT only, no write path.
- Source: audit_events table (Phase 189 migration).
- Default ordering: occurred_at DESC (most recent first).
- Max limit: 100. Default: 50.

Invariants:
- Never reads booking_state, event_log, or booking_financial_facts.
- actor_id defaults to JWT sub (tenant_id alias until Phase 190 user_id wiring).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth, jwt_identity
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100

_VALID_ENTITY_TYPES = frozenset({"task", "booking", "preview", "acting_session"})  # Phase 867+868


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /admin/audit
# ---------------------------------------------------------------------------

@router.get(
    "/admin/audit",
    tags=["audit"],
    summary="List audit events",
    responses={
        200: {"description": "Paginated list of audit events, newest first"},
        401: {"description": "Missing or invalid JWT token"},
        422: {"description": "Invalid query parameter"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_audit_events(
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return audit events for this tenant, newest first.

    **Filters (all optional):**
    - `entity_type` — "task" or "booking"
    - `entity_id`   — specific task_id or booking_id
    - `actor_id`    — filter by the actor who performed the action
    - `limit`       — max records returned (1-100, default 50)

    **Ordering:** `occurred_at DESC`
    """
    # Validate entity_type if supplied
    if entity_type and entity_type not in _VALID_ENTITY_TYPES:
        return make_error_response(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"entity_type must be one of {sorted(_VALID_ENTITY_TYPES)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("audit_events")
            .select("id,tenant_id,actor_id,action,entity_type,entity_id,payload,occurred_at")
            .eq("tenant_id", tenant_id)
        )

        if entity_type:
            query = query.eq("entity_type", entity_type)
        if entity_id:
            query = query.eq("entity_id", entity_id)
        if actor_id:
            query = query.eq("actor_id", actor_id)

        result = (
            query
            .order("occurred_at", desc=True)
            .limit(limit)
            .execute()
        )

        events = result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "count": len(events),
                "events": [
                    {
                        "id":          row.get("id"),
                        "actor_id":    row.get("actor_id"),
                        "action":      row.get("action"),
                        "entity_type": row.get("entity_type"),
                        "entity_id":   row.get("entity_id"),
                        "payload":     row.get("payload", {}),
                        "occurred_at": row.get("occurred_at"),
                    }
                    for row in events
                ],
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/audit error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /manager/audit   — Phase 1033
# ---------------------------------------------------------------------------
# Same data as /admin/audit, but uses jwt_identity so Preview As tokens and
# Act As tokens resolve to the correct role without a secondary DB lookup.
# Allowed roles: admin, manager.

_MANAGER_AUDIT_ROLES = frozenset({"admin", "manager"})


@router.get(
    "/manager/audit",
    tags=["audit"],
    summary="Manager audit events (Phase 1033 — identity-aware)",
    responses={
        200: {"description": "Audit events, newest first"},
        403: {"description": "Role not permitted"},
        422: {"description": "Invalid query parameter"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_manager_audit_events(
    entity_type: Optional[str] = Query(default=None),
    entity_id: Optional[str] = Query(default=None),
    actor_id: Optional[str] = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    identity: dict = Depends(jwt_identity),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /manager/audit

    Phase 1033: identity-aware audit query.
    Resolves role from JWT identity dict — supports Preview As and Act As.

    Allowed: admin, manager.
    Returns all tenant audit events, newest first.
    """
    caller_role = str(identity.get("role", "worker")).strip()

    if caller_role not in _MANAGER_AUDIT_ROLES:
        return make_error_response(
            403, ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Only admin and manager roles can access audit events."},
        )

    if entity_type and entity_type not in _VALID_ENTITY_TYPES:
        return make_error_response(
            status_code=422,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"entity_type must be one of {sorted(_VALID_ENTITY_TYPES)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # No tenant_id scoping — audit_events are cross-tenant from the service role.
        # The admin/manager sees their operational context (all their properties' events).
        query = (
            db.table("audit_events")
            .select("id,tenant_id,actor_id,action,entity_type,entity_id,payload,occurred_at")
        )

        if entity_type:
            query = query.eq("entity_type", entity_type)
        if entity_id:
            query = query.eq("entity_id", entity_id)
        if actor_id:
            query = query.eq("actor_id", actor_id)

        result = (
            query
            .order("occurred_at", desc=True)
            .limit(limit)
            .execute()
        )

        events = result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "role": caller_role,
                "count": len(events),
                "events": [
                    {
                        "id":          row.get("id"),
                        "actor_id":    row.get("actor_id"),
                        "action":      row.get("action"),
                        "entity_type": row.get("entity_type"),
                        "entity_id":   row.get("entity_id"),
                        "payload":     row.get("payload") or {},
                        "occurred_at": row.get("occurred_at"),
                    }
                    for row in events
                ],
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /manager/audit error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
