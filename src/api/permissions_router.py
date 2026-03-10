"""
Phase 165 — Permissions Router

Admin-managed CRUD for tenant_permissions.

Endpoints:
  GET    /permissions                     — list all permissions for the tenant
  GET    /permissions/{user_id}           — get permission record for a user
  POST   /permissions                     — create or upsert a permission record
  DELETE /permissions/{user_id}           — delete a permission record

Rules:
  - JWT auth required (tenant_id from sub claim).
  - Tenant isolation: all operations scoped to tenant_id.
  - Valid roles: admin | manager | worker | owner.
  - permissions field is JSONB; arbitrary capability flags.
  - POST is an upsert (insert or replace on conflict).
  - DELETE returns 404 if the record does not exist.
  - 400 on invalid role.

Enrichment helper (used by auth.py):
  get_permission_record(db, tenant_id, user_id) → dict | None
  Returns the tenant_permissions row for enriching JWT scope.
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

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_ROLES = frozenset({"admin", "manager", "worker", "owner"})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Enrichment helper (also used by auth.py Phase 165)
# ---------------------------------------------------------------------------

def get_permission_record(db: Any, tenant_id: str, user_id: str) -> Optional[dict]:
    """
    Retrieve the tenant_permissions row for (tenant_id, user_id).
    Returns None if no record exists or on any DB error.
    Best-effort: never raises.
    """
    try:
        result = (
            db.table("tenant_permissions")
            .select("role, permissions")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_role(role: Any) -> Optional[JSONResponse]:
    if not isinstance(role, str) or role not in _VALID_ROLES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"role must be one of: {sorted(_VALID_ROLES)}"},
        )
    return None


def _validate_permissions_field(permissions: Any) -> Optional[JSONResponse]:
    if permissions is not None and not isinstance(permissions, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "permissions must be a JSON object (dict)."},
        )
    return None


# ---------------------------------------------------------------------------
# GET /permissions — list all for tenant
# ---------------------------------------------------------------------------

@router.get(
    "/permissions",
    tags=["permissions"],
    summary="List all permission records for the authenticated tenant (Phase 165)",
    responses={
        200: {"description": "List of permission records"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_permissions(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("tenant_permissions")
            .select("id, user_id, role, permissions, created_at, updated_at")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=False)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "tenant_id": tenant_id,
            "count": len(rows),
            "permissions": rows,
        })
    except Exception as exc:
        logger.exception("GET /permissions error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /permissions/{user_id} — get single record
# ---------------------------------------------------------------------------

@router.get(
    "/permissions/{user_id}",
    tags=["permissions"],
    summary="Get permission record for a specific user (Phase 165)",
    responses={
        200: {"description": "Permission record"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Permission record not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_permission(
    user_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("tenant_permissions")
            .select("id, user_id, role, permissions, created_at, updated_at")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.PERMISSION_NOT_FOUND,
                extra={"user_id": user_id},
            )
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("GET /permissions/%s error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /permissions — create / upsert
# ---------------------------------------------------------------------------

@router.post(
    "/permissions",
    tags=["permissions"],
    summary="Create or update a user permission record (Phase 165)",
    description=(
        "Upserts a permission row for a user in the tenant. "
        "Existing records are replaced on conflict (tenant_id, user_id). "
        "**Required:** `user_id`, `role`. "
        "**Optional:** `permissions` (JSONB capability flags)."
    ),
    responses={
        201: {"description": "Permission record created or updated"},
        400: {"description": "Validation error"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_permission(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    user_id = body.get("user_id", "")
    if not user_id or not str(user_id).strip():
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'user_id' is required and must be non-empty."},
        )
    user_id = str(user_id).strip()

    role = body.get("role")
    err = _validate_role(role)
    if err:
        return err

    permissions = body.get("permissions", {})
    err2 = _validate_permissions_field(permissions)
    if err2:
        return err2

    now = datetime.now(tz=timezone.utc).isoformat()

    row = {
        "tenant_id":   tenant_id,
        "user_id":     user_id,
        "role":        role,
        "permissions": permissions if permissions is not None else {},
        "updated_at":  now,
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("tenant_permissions")
            .upsert(row, on_conflict="tenant_id,user_id")
            .execute()
        )
        saved = (result.data or [{}])[0]
        return JSONResponse(status_code=201, content={
            "status":      "upserted",
            "tenant_id":   tenant_id,
            "user_id":     user_id,
            "role":        role,
            "permissions": permissions,
            "updated_at":  now,
        })
    except Exception as exc:
        logger.exception("POST /permissions error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# DELETE /permissions/{user_id}
# ---------------------------------------------------------------------------

@router.delete(
    "/permissions/{user_id}",
    tags=["permissions"],
    summary="Delete a user permission record (Phase 165)",
    responses={
        200: {"description": "Permission record deleted"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Permission record not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def delete_permission(
    user_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()

        # Check existence first
        check = (
            db.table("tenant_permissions")
            .select("user_id")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not (check.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.PERMISSION_NOT_FOUND,
                extra={"user_id": user_id},
            )

        db.table("tenant_permissions") \
            .delete() \
            .eq("tenant_id", tenant_id) \
            .eq("user_id", user_id) \
            .execute()

        return JSONResponse(status_code=200, content={
            "status":    "deleted",
            "tenant_id": tenant_id,
            "user_id":   user_id,
        })
    except Exception as exc:
        logger.exception("DELETE /permissions/%s error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
