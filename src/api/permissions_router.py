"""
Phase 165 — Permissions Router
Phase 167 — Manager Delegated Permissions
Phase 171 — Admin Audit Log (write_audit_event wired into grant/revoke)

Admin-managed CRUD for tenant_permissions.

Endpoints:
  GET    /permissions                           — list all permissions for the tenant
  GET    /permissions/{user_id}                 — get permission record for a user
  POST   /permissions                           — create or upsert a permission record
  DELETE /permissions/{user_id}                 — delete a permission record
  PATCH  /permissions/{user_id}/grant           — Phase 167: grant capability flags
  PATCH  /permissions/{user_id}/revoke          — Phase 167: revoke capability flags

Rules:
  - JWT auth required (tenant_id from sub claim).
  - Tenant isolation: all operations scoped to tenant_id.
  - Valid roles: admin | manager | worker | owner.
  - permissions field is JSONB; arbitrary capability flags.
  - POST is an upsert (insert or replace on conflict).
  - DELETE returns 404 if the record does not exist.
  - 400 on invalid role.

Grant/Revoke (Phase 167):
  - PATCH /permissions/{user_id}/grant  body: {"capabilities": {"flag": value, ...}}
    Merges supplied flags into the existing permissions JSONB (shallow merge).
    Creates record if missing (with role='manager' default unless user has a record).
    Returns 404 if no existing permission record for user_id.
  - PATCH /permissions/{user_id}/revoke body: {"capabilities": ["flag", ...]}
    Removes listed keys from the existing permissions JSONB.
    Returns 404 if no existing permission record.
    Returns 200 even if some keys were not present (idempotent).

Known capability flags (non-exhaustive):
  can_approve_owner_statements  bool
  can_manage_integrations       bool
  can_view_financials           bool
  can_manage_workers            bool
  worker_role                   str   (WorkerRole value — for worker-scoped tasks)
  property_ids                  list  (for owner-scoped properties)

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


# ---------------------------------------------------------------------------
# Phase 167 helpers
# ---------------------------------------------------------------------------

def _fetch_existing_permissions(db: Any, tenant_id: str, user_id: str) -> Optional[dict]:
    """Fetch the current permissions JSONB for (tenant_id, user_id). Returns None if missing."""
    try:
        result = (
            db.table("tenant_permissions")
            .select("permissions")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        return rows[0].get("permissions") or {}
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# PATCH /permissions/{user_id}/grant
# ---------------------------------------------------------------------------

@router.patch(
    "/permissions/{user_id}/grant",
    tags=["permissions"],
    summary="Grant capability flags to a user (Phase 167)",
    description=(
        "Merges the supplied capability flags into the user's permissions JSONB. "
        "Existing flags not listed in the body are preserved. "
        "**Required body:** `{\"capabilities\": {\"flag\": value, ...}}`. "
        "Returns 404 if no permission record exists for the user."
    ),
    responses={
        200: {"description": "Capabilities granted"},
        400: {"description": "Validation error"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Permission record not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def grant_permission(
    user_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Grant capability flags to an existing user permission record.

    **Body:**
    ```json
    {"capabilities": {"can_approve_owner_statements": true, "can_view_financials": true}}
    ```

    Flags are merged (shallow) into the existing `permissions` JSONB.
    Existing flags NOT in this payload are preserved.
    Returns **404** if the user has no permission record — create one first
    via `POST /permissions`.
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    capabilities = body.get("capabilities")
    if not isinstance(capabilities, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'capabilities' must be a JSON object (dict of flag: value)."},
        )

    if not capabilities:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'capabilities' must be non-empty."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        existing_perms = _fetch_existing_permissions(db, tenant_id, user_id)
        if existing_perms is None:
            return make_error_response(
                status_code=404,
                code=ErrorCode.PERMISSION_NOT_FOUND,
                extra={"user_id": user_id},
            )

        # Shallow merge: existing flags preserved, new flags overlay
        merged = {**existing_perms, **capabilities}
        now = datetime.now(tz=timezone.utc).isoformat()

        db.table("tenant_permissions") \
            .update({"permissions": merged, "updated_at": now}) \
            .eq("tenant_id", tenant_id) \
            .eq("user_id", user_id) \
            .execute()

        # Phase 171 — audit trail (best-effort, never raises)
        try:
            from api.admin_router import write_audit_event  # noqa: PLC0415
            write_audit_event(
                db,
                tenant_id=tenant_id,
                actor_user_id=tenant_id,   # JWT sub is the actor
                action="grant_permission",
                target_type="permission",
                target_id=user_id,
                before_state={"permissions": existing_perms},
                after_state={"permissions": merged},
                metadata={"granted_flags": list(capabilities.keys())},
            )
        except Exception:  # noqa: BLE001
            pass

        return JSONResponse(status_code=200, content={
            "status":           "granted",
            "tenant_id":        tenant_id,
            "user_id":          user_id,
            "granted":          capabilities,
            "permissions":      merged,
            "updated_at":       now,
        })
    except Exception as exc:
        logger.exception("PATCH /permissions/%s/grant error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PATCH /permissions/{user_id}/revoke
# ---------------------------------------------------------------------------

@router.patch(
    "/permissions/{user_id}/revoke",
    tags=["permissions"],
    summary="Revoke capability flags from a user (Phase 167)",
    description=(
        "Removes the listed capability flag keys from the user's permissions JSONB. "
        "Keys not present are ignored (idempotent). "
        "**Required body:** `{\"capabilities\": [\"flag_name\", ...]}`. "
        "Returns 404 if no permission record exists for the user."
    ),
    responses={
        200: {"description": "Capabilities revoked"},
        400: {"description": "Validation error"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Permission record not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def revoke_permission(
    user_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Revoke (remove) specific capability flags from a user's permissions record.

    **Body:**
    ```json
    {"capabilities": ["can_approve_owner_statements", "can_view_financials"]}
    ```

    Keys not present in the current permissions are silently ignored (idempotent).
    Returns **404** if the user has no permission record.
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    capabilities = body.get("capabilities")
    if not isinstance(capabilities, list):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'capabilities' must be a JSON array of flag names."},
        )

    if not capabilities:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'capabilities' must be non-empty."},
        )

    # All entries must be strings
    if not all(isinstance(k, str) for k in capabilities):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "All entries in 'capabilities' must be strings."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        existing_perms = _fetch_existing_permissions(db, tenant_id, user_id)
        if existing_perms is None:
            return make_error_response(
                status_code=404,
                code=ErrorCode.PERMISSION_NOT_FOUND,
                extra={"user_id": user_id},
            )

        # Remove listed keys; keys not present are silently ignored
        actually_revoked = [k for k in capabilities if k in existing_perms]
        remaining = {k: v for k, v in existing_perms.items() if k not in capabilities}
        now = datetime.now(tz=timezone.utc).isoformat()

        db.table("tenant_permissions") \
            .update({"permissions": remaining, "updated_at": now}) \
            .eq("tenant_id", tenant_id) \
            .eq("user_id", user_id) \
            .execute()

        # Phase 171 — audit trail (best-effort, never raises)
        try:
            from api.admin_router import write_audit_event  # noqa: PLC0415
            write_audit_event(
                db,
                tenant_id=tenant_id,
                actor_user_id=tenant_id,
                action="revoke_permission",
                target_type="permission",
                target_id=user_id,
                before_state={"permissions": existing_perms},
                after_state={"permissions": remaining},
                metadata={"revoked_flags": actually_revoked},
            )
        except Exception:  # noqa: BLE001
            pass

        return JSONResponse(status_code=200, content={
            "status":           "revoked",
            "tenant_id":        tenant_id,
            "user_id":          user_id,
            "revoked":          actually_revoked,
            "ignored":          [k for k in capabilities if k not in existing_perms],
            "permissions":      remaining,
            "updated_at":       now,
        })
    except Exception as exc:
        logger.exception("PATCH /permissions/%s/revoke error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
