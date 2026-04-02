"""
Phase 165 — Permissions Router
Phase 167 — Manager Delegated Permissions
Phase 171 — Admin Audit Log (write_audit_event wired into grant/revoke)
Phase 842 — Staff Schema Extension
  - Extended GET endpoints to return new profile columns
  - Added PATCH /permissions/{user_id} partial profile update
  - Added GET/POST/DELETE /staff/assignments for property assignment management

Admin-managed CRUD for tenant_permissions.

Endpoints:
  GET    /permissions                           — list all permissions for the tenant
  GET    /permissions/{user_id}                 — get permission record for a user
  POST   /permissions                           — create or upsert a permission record
  PATCH  /permissions/{user_id}                 — Phase 842: partial profile field update
  DELETE /permissions/{user_id}                 — delete a permission record
  PATCH  /permissions/{user_id}/grant           — Phase 167: grant capability flags
  PATCH  /permissions/{user_id}/revoke          — Phase 167: revoke capability flags
  GET    /staff/assignments/{user_id}           — Phase 842: list property assignments
  POST   /staff/assignments                     — Phase 842: add property assignment
  DELETE /staff/assignments/{user_id}/{prop_id} — Phase 842: remove property assignment

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

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# Phase 862 (Canonical Auth P7): single source of truth for roles
from services.canonical_roles import CANONICAL_ROLES as _VALID_ROLES


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


def _sync_channels(db: Any, tenant_id: str, user_id: str, comm_preference: dict) -> None:
    """
    Sync a worker's comm_preference dictionary to the notification_channels table.
    Ensures that the dispatcher (which reads from notification_channels) is always
    kept in sync when the Admin UI updates the worker profile.
    """
    if not isinstance(comm_preference, dict):
        return
    try:
        from channels.notification_dispatcher import register_channel, deregister_channel
        for ch_type in {"line", "whatsapp", "telegram", "sms", "email"}:
            val = comm_preference.get(ch_type)
            val_str = str(val).strip() if val else ""
            if val_str:
                register_channel(db, tenant_id, user_id, ch_type, val_str)
            else:
                deregister_channel(db, tenant_id, user_id, ch_type)
    except Exception as exc:
        logger.exception("Failed to sync comm_preference to notification_channels: %s", exc)

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
            .select(
                "id, user_id, role, permissions, display_name, phone, language,"
                " worker_id, worker_role,"
                " photo_url, address, emergency_contact, comm_preference,"
                " worker_roles, maintenance_specializations, notes, is_active,"
                # Phase 1025 Fix E: dedicated PII columns (Phase 857 migration)
                " date_of_birth, id_number, id_expiry_date, id_photo_url,"
                " work_permit_number, work_permit_expiry_date, work_permit_photo_url,"
                " created_at, updated_at"
            )
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
# GET /permissions/me — caller's own permission record (Phase 1032)
# Used by the worker home page to read comm_preference._promotion_notice
# Must be registered BEFORE /permissions/{user_id} to avoid path shadowing.
# ---------------------------------------------------------------------------

@router.get(
    "/permissions/me",
    tags=["permissions"],
    summary="Get the calling user's own permission record (Phase 1032)",
    responses={
        200: {"description": "Caller's permission record including comm_preference"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No permission record found for this user"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_my_permission(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Returns the permission record for the authenticated user (self lookup).
    Includes comm_preference which contains _promotion_notice for the worker
    promotion banner on the worker home page.
    """
    try:
        # Extract the caller's user_id from JWT
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()
        import jwt as _jwt
        try:
            payload = _jwt.decode(token, options={"verify_signature": False})
            caller_user_id = payload.get("sub") or payload.get("user_id")
        except Exception:
            return make_error_response(status_code=401, code=ErrorCode.UNAUTHORIZED,
                                       extra={"detail": "Cannot decode user identity from token."})

        if not caller_user_id:
            return make_error_response(status_code=401, code=ErrorCode.UNAUTHORIZED,
                                       extra={"detail": "Token contains no user identity."})

        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("tenant_permissions")
            .select(
                "id, user_id, role, permissions, display_name, phone, language,"
                " worker_id, worker_role,"
                " photo_url, comm_preference,"
                " worker_roles, is_active,"
                " created_at, updated_at"
            )
            .eq("tenant_id", tenant_id)
            .eq("user_id", caller_user_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code=ErrorCode.NOT_FOUND,
                                       extra={"detail": f"No permission record for user {caller_user_id}"})

        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("GET /permissions/me error: %s", exc)
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
            .select(
                "id, user_id, role, permissions, display_name, phone, language,"
                " worker_id, worker_role,"
                " photo_url, address, emergency_contact, comm_preference,"
                " worker_roles, maintenance_specializations, notes, is_active,"
                # Phase 1025 Fix E: dedicated PII columns (Phase 857 migration)
                " date_of_birth, id_number, id_expiry_date, id_photo_url,"
                " work_permit_number, work_permit_expiry_date, work_permit_photo_url,"
                " created_at, updated_at"
            )
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

    row: dict = {
        "tenant_id":   tenant_id,
        "user_id":     user_id,
        "role":        role,
        "permissions": permissions if permissions is not None else {},
        "updated_at":  now,
    }

    # Phase 842: include optional profile fields when provided
    _PROFILE_FIELDS = (
        "display_name", "phone", "language",
        "photo_url", "address", "emergency_contact",
        "comm_preference", "worker_roles", "maintenance_specializations",
        "notes", "is_active",
    )
    for field in _PROFILE_FIELDS:
        if field in body:
            row[field] = body[field]

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("tenant_permissions")
            .upsert(row, on_conflict="tenant_id,user_id")
            .execute()
        )
        saved = (result.data or [{}])[0]
        
        # Sync notification_channels if comm_preference was modified
        if "comm_preference" in body:
            _sync_channels(db, tenant_id, user_id, body["comm_preference"])

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


# ---------------------------------------------------------------------------
# PATCH /permissions/{user_id} — Phase 842: partial profile field update
# ---------------------------------------------------------------------------

# Profile fields that can be partially updated (PATCH semantics)
_PATCHABLE_PROFILE_FIELDS = frozenset({
    "display_name", "phone", "language",
    "photo_url", "address", "emergency_contact",
    "comm_preference", "worker_roles", "maintenance_specializations",
    "notes", "is_active", "role",
    # Phase 1025 Fix E: dedicated PII columns — patchable by admin
    "date_of_birth", "id_number", "id_expiry_date", "id_photo_url",
    "work_permit_number", "work_permit_expiry_date", "work_permit_photo_url",
})

@router.patch(
    "/permissions/{user_id}",
    tags=["permissions"],
    summary="Partially update a staff profile record (Phase 842)",
    description=(
        "Updates only the supplied fields on an existing tenant_permissions row. "
        "Unlike POST /permissions (which upserts the whole record), this PATCH applies "
        "only the fields present in the request body. "
        "Updateable fields: display_name, phone, language, photo_url, address, "
        "emergency_contact, comm_preference, worker_roles, maintenance_specializations, "
        "notes, is_active, role. "
        "The permissions JSONB flags use /grant and /revoke instead."
    ),
    responses={
        200: {"description": "Profile fields updated"},
        400: {"description": "Validation error — no valid fields, or invalid role"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Permission record not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def patch_permission_profile(
    user_id: str,
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

    # Extract only recognised, patchable fields from the body
    updates: dict = {k: v for k, v in body.items() if k in _PATCHABLE_PROFILE_FIELDS}
    if not updates:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"No patchable fields found. Allowed: {sorted(_PATCHABLE_PROFILE_FIELDS)}"},
        )

    # Validate role if being changed
    if "role" in updates:
        err = _validate_role(updates["role"])
        if err:
            return err

    try:
        db = client if client is not None else _get_supabase_client()

        # Verify record exists
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

        now = datetime.now(tz=timezone.utc).isoformat()
        updates["updated_at"] = now

        result = (
            db.table("tenant_permissions")
            .update(updates)
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .execute()
        )
        saved = (result.data or [{}])[0]
        
        # Sync notification_channels if comm_preference was modified
        if "comm_preference" in updates:
            _sync_channels(db, tenant_id, user_id, updates["comm_preference"])

        return JSONResponse(status_code=200, content={
            "status":     "updated",
            "tenant_id":  tenant_id,
            "user_id":    user_id,
            "updated":    list(updates.keys()),
            "updated_at": now,
        })
    except Exception as exc:
        logger.exception("PATCH /permissions/%s error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 842 — Staff Property Assignment Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/staff/assignments/{user_id}",
    tags=["staff"],
    summary="List property assignments for a staff member (Phase 842)",
    responses={
        200: {"description": "List of assigned property IDs"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_staff_assignments(
    user_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("staff_property_assignments")
            .select("id, property_id, assigned_at, assigned_by")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .order("assigned_at", desc=False)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "tenant_id":    tenant_id,
            "user_id":      user_id,
            "count":        len(rows),
            "assignments":  rows,
            "property_ids": [r["property_id"] for r in rows],
        })
    except Exception as exc:
        logger.exception("GET /staff/assignments/%s error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 888: Task Assignment Backfill
# ---------------------------------------------------------------------------
# Product rules:
#   ON ASSIGN:  Backfill future PENDING tasks where assigned_to IS NULL
#               and worker_role matches the new assignee's roles.
#   ON UNASSIGN: Clear assigned_to on future PENDING tasks that were
#               assigned to the removed user. ACKNOWLEDGED / IN_PROGRESS
#               tasks are NEVER touched (they require human decisions).
#   SCOPE:      Only tasks with due_date >= today, status = PENDING,
#               and matching property_id.
# ---------------------------------------------------------------------------

# Maps UI-stored lowercase roles → task system uppercase WorkerRole values
_ROLE_TO_TASK_ROLES: dict = {
    "cleaner":     ["CLEANER"],
    "checkin":     ["CHECKIN", "PROPERTY_MANAGER"],
    "checkout":    ["CHECKOUT", "INSPECTOR"],
    "maintenance": ["MAINTENANCE", "MAINTENANCE_TECH"],
}


def _backfill_tasks_on_assign(
    db: Any,
    tenant_id: str,
    user_id: str,
    property_id: str,
) -> dict:
    """Backfill future PENDING unassigned tasks when a staff member is assigned to a property.

    Returns: {"backfilled": int, "roles_matched": list, "task_ids": list}
    """
    from datetime import date
    today = date.today().isoformat()

    try:
        # 1. Get the worker's roles from tenant_permissions
        perm_res = (
            db.table("tenant_permissions")
            .select("worker_roles")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        perm_rows = perm_res.data or []
        if not perm_rows:
            return {"backfilled": 0, "roles_matched": [], "task_ids": [], "reason": "no_permissions_record"}

        ui_roles = perm_rows[0].get("worker_roles") or []
        if not ui_roles:
            return {"backfilled": 0, "roles_matched": [], "task_ids": [], "reason": "no_worker_roles"}

        # 2. Map UI roles to task-system worker_role values
        task_roles = []
        for ui_role in ui_roles:
            task_roles.extend(_ROLE_TO_TASK_ROLES.get(ui_role.lower(), []))
        task_roles = list(set(task_roles))  # deduplicate

        if not task_roles:
            return {"backfilled": 0, "roles_matched": [], "task_ids": [], "reason": "no_matching_task_roles"}

        # 3. Find future PENDING unassigned tasks on this property with matching roles
        query = (
            db.table("tasks")
            .select("task_id, worker_role, due_date")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("status", "PENDING")
            .is_("assigned_to", "null")
            .gte("due_date", today)
            .in_("worker_role", task_roles)
            .limit(200)
        )
        task_res = query.execute()
        matching_tasks = task_res.data or []

        if not matching_tasks:
            return {"backfilled": 0, "roles_matched": task_roles, "task_ids": []}

        # Phase 1031-fix: Primary-existence guard.
        # If NULL tasks exist but a priority=1 worker already covers this lane,
        # those NULLs are a healing problem — the Primary should own them, not
        # the newly added Backup. Backfilling the Backup would silently misassign them.
        #
        # Rule: if the new worker is NOT priority=1, and a priority=1 worker already
        # exists on this property with at least one matching task_role, skip backfill
        # for the NULL tasks. They will be picked up by the existing primary-assignment
        # path (booking creation, amendment, or ad-hoc creation all use ORDER BY priority ASC).
        # Future tasks generated AFTER this backfill call will be assigned to the Primary via
        # the task_writer — so this guard does not leave tasks permanently ownerless.
        try:
            new_worker_priority_res = (
                db.table("staff_property_assignments")
                .select("priority")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .eq("property_id", property_id)
                .limit(1)
                .execute()
            )
            new_worker_priority = (new_worker_priority_res.data or [{}])[0].get("priority", 1)

            if new_worker_priority != 1:
                # Check if a Primary (priority=1) already exists for a matching lane
                primary_res = (
                    db.table("staff_property_assignments")
                    .select("user_id, priority")
                    .eq("tenant_id", tenant_id)
                    .eq("property_id", property_id)
                    .eq("priority", 1)
                    .neq("user_id", user_id)
                    .limit(10)
                    .execute()
                )
                primary_ids = [r["user_id"] for r in (primary_res.data or [])]
                if primary_ids:
                    primary_roles_res = (
                        db.table("tenant_permissions")
                        .select("user_id, worker_roles")
                        .eq("tenant_id", tenant_id)
                        .in_("user_id", primary_ids)
                        .execute()
                    )
                    for pr in (primary_roles_res.data or []):
                        primary_task_roles = []
                        for pr_ui in (pr.get("worker_roles") or []):
                            primary_task_roles.extend(_ROLE_TO_TASK_ROLES.get(pr_ui.lower(), []))
                        if set(primary_task_roles) & set(task_roles):
                            # A Primary exists for this lane — do not backfill the Backup
                            logger.info(
                                "task_backfill: skipping backfill for Backup user=%s property=%s "
                                "— Primary already exists for this lane (roles: %s). "
                                "NULL tasks belong to the Primary assignment path.",
                                user_id, property_id, task_roles,
                            )
                            return {"backfilled": 0, "roles_matched": task_roles, "task_ids": [],
                                    "reason": "primary_exists_for_lane"}
        except Exception as _guard_exc:
            logger.warning("task_backfill: primary-exists guard failed for %s/%s: %s", user_id, property_id, _guard_exc)
            # If guard fails, proceed with backfill so we don't silently orphan tasks

        # 4. Batch update: assign all matching tasks to this worker
        task_ids = [t["task_id"] for t in matching_tasks]
        now = datetime.now(tz=timezone.utc).isoformat()

        db.table("tasks").update({
            "assigned_to": user_id,
            "updated_at": now,
        }).in_("task_id", task_ids).eq("status", "PENDING").is_("assigned_to", "null").execute()

        logger.info(
            "task_backfill: assigned %d future PENDING tasks to %s for property %s (roles: %s)",
            len(task_ids), user_id, property_id, task_roles,
        )

        # 5. Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="task_backfill",
                              entity_id=property_id, action="assignment_backfill",
                              details={"user_id": user_id, "tasks_backfilled": len(task_ids),
                                       "roles": task_roles, "task_ids": task_ids[:20]})
        except Exception:
            pass

        return {"backfilled": len(task_ids), "roles_matched": task_roles, "task_ids": task_ids}

    except Exception as exc:
        logger.warning("task_backfill: assignment backfill failed for %s/%s: %s", user_id, property_id, exc)
        return {"backfilled": 0, "error": str(exc)}


def _clear_tasks_on_unassign(
    db: Any,
    tenant_id: str,
    user_id: str,
    property_id: str,
) -> dict:
    """Clear assigned_to on future PENDING tasks when a staff member is unassigned.

    ONLY clears PENDING tasks. ACKNOWLEDGED and IN_PROGRESS tasks are never
    touched — those represent active human commitments.

    Returns: {"cleared": int, "task_ids": list}
    """
    from datetime import date
    today = date.today().isoformat()

    try:
        # Find future PENDING tasks assigned to this user on this property
        task_res = (
            db.table("tasks")
            .select("task_id, worker_role, due_date")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("status", "PENDING")
            .eq("assigned_to", user_id)
            .gte("due_date", today)
            .limit(200)
            .execute()
        )
        matching_tasks = task_res.data or []

        if not matching_tasks:
            return {"cleared": 0, "task_ids": []}

        task_ids = [t["task_id"] for t in matching_tasks]
        now = datetime.now(tz=timezone.utc).isoformat()

        db.table("tasks").update({
            "assigned_to": None,
            "updated_at": now,
        }).in_("task_id", task_ids).eq("status", "PENDING").eq("assigned_to", user_id).execute()

        logger.info(
            "task_backfill: cleared %d future PENDING tasks from %s for property %s",
            len(task_ids), user_id, property_id,
        )

        # Audit
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(db, tenant_id=tenant_id, entity_type="task_backfill",
                              entity_id=property_id, action="unassignment_clear",
                              details={"user_id": user_id, "tasks_cleared": len(task_ids),
                                       "task_ids": task_ids[:20]})
        except Exception:
            pass

        return {"cleared": len(task_ids), "task_ids": task_ids}

    except Exception as exc:
        logger.warning("task_backfill: unassignment clear failed for %s/%s: %s", user_id, property_id, exc)
        return {"cleared": 0, "error": str(exc)}


@router.post(
    "/staff/assignments",
    tags=["staff"],
    summary="Assign a property to a staff member (Phase 842)",
    description="Body: {user_id, property_id}. Idempotent — duplicate assignments are silently ignored.",
    responses={
        201: {"description": "Assignment created"},
        400: {"description": "Validation error"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_staff_assignment(
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

    user_id = str(body.get("user_id", "")).strip()
    property_id = str(body.get("property_id", "")).strip()

    if not user_id or not property_id:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'user_id' and 'property_id' are required."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # Phase 887d: Enforce the "Approved-Only" operational rule.
        # A property must be in 'approved' status before any staff can be assigned to it.
        # Pending, draft, archived, and rejected properties are non-operational.
        prop_check = (
            db.table("properties")
            .select("property_id, status")
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        prop_rows = prop_check.data or []
        if not prop_rows:
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"Property '{property_id}' not found."},
            )
        prop_status = prop_rows[0].get("status", "")
        if prop_status != "approved":
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={
                    "detail": (
                        f"Property '{property_id}' has status '{prop_status}' and cannot be assigned to staff. "
                        "Only 'approved' properties may be operationally assigned."
                    )
                },
            )

        # Phase 1031 — Lane-aware priority assignment.
        # The Primary/Backup model requires a unique, ordered priority per (property, lane).
        # We must NOT use DEFAULT 1 for every new assignment — that creates flat priority=1
        # for all workers and breaks deterministic Primary selection.
        #
        # Lane definitions (locked):
        #   CLEANING:         worker_roles contains 'cleaner'
        #   MAINTENANCE:      worker_roles contains 'maintenance'
        #   CHECKIN_CHECKOUT: worker_roles contains 'checkin' OR 'checkout' (shared lane)
        #   UNKNOWN:          no recognized roles (admin/ops accounts) — starts at priority 100
        #
        # Algorithm:
        #   1. Look up the worker's roles to determine their lane.
        #   2. Find MAX(priority) for that lane on this property.
        #   3. Assign MAX + 1 (i.e., they become the last Backup in the stack).
        #   4. If this is an upsert (worker already assigned), do NOT change their priority.
        computed_priority = 1  # safe fallback — overwritten below
        is_new_assignment = True
        try:
            # Check if already assigned (upsert case — don't change priority)
            existing = (
                db.table("staff_property_assignments")
                .select("priority")
                .eq("tenant_id", tenant_id)
                .eq("user_id", user_id)
                .eq("property_id", property_id)
                .limit(1)
                .execute()
            )
            if existing.data:
                is_new_assignment = False
                computed_priority = existing.data[0].get("priority", 1)
            else:
                # Resolve the user's system role AND worker_roles in one query.
                # Phase 1038: Differentiate between supervisory roles and workers.
                # Supervisory roles (manager, admin, owner) get a flat priority=100
                # and bypass lane logic entirely — they are scope assignments, not lane slots.
                roles_res = (
                    db.table("tenant_permissions")
                    .select("worker_roles, role")
                    .eq("tenant_id", tenant_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                perm_row = (roles_res.data or [{}])[0]
                worker_roles = perm_row.get("worker_roles") or []
                sys_role = perm_row.get("role", "")

                # ── Supervisory bypass ─────────────────────────────────────────
                # manager / admin / owner are supervisory-scope assignments.
                # They do NOT enter the worker lane stack and do NOT need worker_roles.
                # The DB trigger (fn_guard_assignment_requires_operational_lane) already
                # permits these roles (Phase 1033). We just need to not reject them here.
                if sys_role in ("manager", "admin", "owner"):
                    computed_priority = 100  # neutral supervisor slot — never conflicts with worker lanes 1-N
                    logger.info(
                        "post_staff_assignment: supervisory assignment — user=%s role=%s property=%s priority=100",
                        user_id, sys_role, property_id,
                    )

                # ── Worker lane resolution ─────────────────────────────────────
                elif "cleaner" in worker_roles:
                    lane = "CLEANING"
                    lane_filter_col = "cleaner"
                    lane_filter_type = "contains"
                    # Compute next priority via DB function
                    try:
                        fn_res = db.rpc(
                            "get_next_lane_priority",
                            {"p_tenant_id": tenant_id, "p_property_id": property_id, "p_lane": lane}
                        ).execute()
                        computed_priority = fn_res.data if isinstance(fn_res.data, int) else 1
                    except Exception as _fn_exc:
                        logger.warning(
                            "post_staff_assignment: get_next_lane_priority RPC failed lane=%s: %s. Fallback to 1.",
                            lane, _fn_exc,
                        )
                        computed_priority = 1
                    logger.info(
                        "post_staff_assignment: user=%s property=%s lane=%s → priority=%d (new=True)",
                        user_id, property_id, lane, computed_priority,
                    )
                elif "maintenance" in worker_roles:
                    lane = "MAINTENANCE"
                    lane_filter_col = "maintenance"
                    lane_filter_type = "contains"
                    try:
                        fn_res = db.rpc(
                            "get_next_lane_priority",
                            {"p_tenant_id": tenant_id, "p_property_id": property_id, "p_lane": lane}
                        ).execute()
                        computed_priority = fn_res.data if isinstance(fn_res.data, int) else 1
                    except Exception as _fn_exc:
                        logger.warning(
                            "post_staff_assignment: get_next_lane_priority RPC failed lane=%s: %s. Fallback to 1.",
                            lane, _fn_exc,
                        )
                        computed_priority = 1
                    logger.info(
                        "post_staff_assignment: user=%s property=%s lane=%s → priority=%d (new=True)",
                        user_id, property_id, lane, computed_priority,
                    )
                elif "checkin" in worker_roles or "checkout" in worker_roles:
                    lane = "CHECKIN_CHECKOUT"
                    lane_filter_col = None
                    lane_filter_type = "overlap"
                    try:
                        fn_res = db.rpc(
                            "get_next_lane_priority",
                            {"p_tenant_id": tenant_id, "p_property_id": property_id, "p_lane": lane}
                        ).execute()
                        computed_priority = fn_res.data if isinstance(fn_res.data, int) else 1
                    except Exception as _fn_exc:
                        logger.warning(
                            "post_staff_assignment: get_next_lane_priority RPC failed lane=%s: %s. Fallback to 1.",
                            lane, _fn_exc,
                        )
                        computed_priority = 1
                    logger.info(
                        "post_staff_assignment: user=%s property=%s lane=%s → priority=%d (new=True)",
                        user_id, property_id, lane, computed_priority,
                    )
                else:
                    # True worker with no recognized operational lane.
                    # This is a configuration error — reject with clear message.
                    if not roles_res.data:
                        detail = (
                            f"Staff member '{user_id}' has no tenant_permissions record. "
                            "This user does not exist in the system. "
                            "Create the user before assigning them to a property."
                        )
                    else:
                        detail = (
                            f"Staff member '{user_id}' (role='{sys_role}') has no operational lane "
                            "(worker_roles is empty or unrecognized). "
                            "Workers must have at least one of: cleaner, maintenance, checkin, checkout. "
                            "Supervisory roles (manager, admin, owner) do not need worker_roles — "
                            "if this person has a supervisory role, please save the profile Role first, "
                            "then assign properties."
                        )
                    logger.warning(
                        "post_staff_assignment: BLOCKED — user=%s role=%s has no valid lane for property=%s. "
                        "worker_roles=%s",
                        user_id, sys_role, property_id, worker_roles,
                    )
                    return make_error_response(
                        status_code=400,
                        code="NO_OPERATIONAL_LANE",
                        extra={
                            "detail": detail,
                            "user_id": user_id,
                            "property_id": property_id,
                            "sys_role": sys_role,
                            "worker_roles_found": worker_roles,
                            "valid_worker_roles": ["cleaner", "maintenance", "checkin", "checkout"],
                            "valid_supervisory_roles": ["manager", "admin", "owner"],
                        },
                    )
        except Exception as _priority_exc:
            # If the lane-resolution block itself failed (network/DB error), do NOT
            # silently fall back to priority=1. That would create a corrupt assignment.
            # Instead, re-raise so the outer handler returns 500 — visible failure.
            logger.error(
                "post_staff_assignment: FATAL — lane resolution failed for user=%s property=%s: %s. "
                "Assignment aborted. This is not a silent fallback.",
                user_id, property_id, _priority_exc,
            )
            raise

        actor_id = body.get("assigned_by", tenant_id)
        row = {
            "tenant_id":   tenant_id,
            "user_id":     user_id,
            "property_id": property_id,
            "assigned_by": actor_id,
            # Phase 1032 fix: always include priority in the upsert payload.
            # PostgREST upsert sends all payload fields in the INSERT attempt —
            # missing fields become NULL which violates chk_priority_positive.
            # computed_priority is always set: existing-row uses current value
            # (idempotent update), new-row uses the lane-aware computed value.
            "priority":    computed_priority,
        }

        # Upsert — UNIQUE(tenant_id, user_id, property_id) handles duplicates
        result = (
            db.table("staff_property_assignments")
            .upsert(row, on_conflict="tenant_id,user_id,property_id")
            .execute()
        )
        saved = (result.data or [{}])[0]

        # Phase 888 + 1031: Backfill future PENDING tasks
        # The primary-existence guard in _backfill_tasks_on_assign ensures Backup workers
        # don't steal NULL tasks when a Primary already covers the lane.
        backfill_result = _backfill_tasks_on_assign(db, tenant_id, user_id, property_id)

        return JSONResponse(status_code=201, content={
            "status":            "assigned",
            "tenant_id":         tenant_id,
            "user_id":           user_id,
            "property_id":       property_id,
            "id":                saved.get("id"),
            "priority_assigned": computed_priority,
            "is_new_assignment": is_new_assignment,
            "tasks_backfilled":  backfill_result.get("backfilled", 0),
            "backfill_detail":   backfill_result,
        })
    except Exception as exc:
        logger.exception("POST /staff/assignments error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.delete(
    "/staff/assignments/{user_id}/{property_id}",
    tags=["staff"],
    summary="Remove a property assignment from a staff member (Phase 1030: baton-transfer)",
    responses={
        200: {"description": "Assignment removed, baton-transfer executed if applicable"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Assignment not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def delete_staff_assignment(
    user_id: str,
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()

        # Check existence and fetch priority of the removed worker
        check = (
            db.table("staff_property_assignments")
            .select("id, priority")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        if not (check.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.PERMISSION_NOT_FOUND,
                extra={"user_id": user_id, "property_id": property_id},
            )

        removed_priority = (check.data or [{}])[0].get("priority", 1)
        is_primary = (removed_priority == 1)

        # Phase 1030: Baton-transfer — execute BEFORE deleting the row
        baton_result = {"transfer_occurred": False, "new_primary_user_id": None, "tasks_transferred": 0}
        if is_primary:
            baton_result = _execute_baton_transfer(db, tenant_id, user_id, property_id)

        # Delete the assignment
        db.table("staff_property_assignments") \
            .delete() \
            .eq("tenant_id", tenant_id) \
            .eq("user_id", user_id) \
            .eq("property_id", property_id) \
            .execute()

        # Phase 888: Clear remaining future PENDING tasks that were NOT transferred
        # (non-primary removals, or tasks not matching the new primary's roles)
        clear_result = _clear_tasks_on_unassign(db, tenant_id, user_id, property_id)

        # Write audit log
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                db, tenant_id=tenant_id, entity_type="staff_assignment",
                entity_id=property_id, action="primary_removed" if is_primary else "backup_removed",
                details={
                    "removed_user_id": user_id, "was_primary": is_primary,
                    "baton_transfer": baton_result, "tasks_cleared": clear_result.get("cleared", 0),
                }
            )
        except Exception:
            pass

        return JSONResponse(status_code=200, content={
            "status":            "unassigned",
            "tenant_id":         tenant_id,
            "user_id":           user_id,
            "property_id":       property_id,
            "was_primary":       is_primary,
            "baton_transfer":    baton_result,
            "tasks_cleared":     clear_result.get("cleared", 0),
            "clear_detail":      clear_result,
        })
    except Exception as exc:
        logger.exception("DELETE /staff/assignments/%s/%s error: %s", user_id, property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 1030 — New endpoint: preview the impact of removing a primary
# Used by the UI confirmation modal before the admin confirms primary removal.
# ---------------------------------------------------------------------------

@router.get(
    "/staff/assignments/{user_id}/{property_id}/removal-preview",
    tags=["staff"],
    summary="Preview what happens if this worker is removed from property (Phase 1030)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def preview_staff_removal(
    user_id: str,
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Returns a preview of the baton-transfer consequences WITHOUT any writes."""
    try:
        db = client if client is not None else _get_supabase_client()
        from datetime import date
        today = date.today().isoformat()

        # 1. Get removed worker's priority and display name
        spa_res = (
            db.table("staff_property_assignments")
            .select("priority")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        if not (spa_res.data or []):
            return make_error_response(status_code=404, code=ErrorCode.PERMISSION_NOT_FOUND)

        removed_priority = (spa_res.data or [{}])[0].get("priority", 1)
        is_primary = (removed_priority == 1)

        # Get removed worker name
        name_res = (
            db.table("tenant_permissions")
            .select("display_name, worker_roles")
            .eq("tenant_id", tenant_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        removed_name = (name_res.data or [{}])[0].get("display_name", user_id)
        removed_roles = (name_res.data or [{}])[0].get("worker_roles") or []

        # 2. Find next backup (priority=2 or lowest priority > removed_priority)
        next_backup = None
        new_primary_name = None
        if is_primary:
            next_res = (
                db.table("staff_property_assignments")
                .select("user_id, priority")
                .eq("tenant_id", tenant_id)
                .eq("property_id", property_id)
                .neq("user_id", user_id)
                .order("priority", desc=False)
                .limit(1)
                .execute()
            )
            if next_res.data:
                next_backup = next_res.data[0]["user_id"]
                nb_res = (
                    db.table("tenant_permissions")
                    .select("display_name")
                    .eq("tenant_id", tenant_id)
                    .eq("user_id", next_backup)
                    .limit(1)
                    .execute()
                )
                new_primary_name = (nb_res.data or [{}])[0].get("display_name", next_backup)

        # 3. Count PENDING tasks that would transfer to new primary
        pending_count = 0
        if next_backup:
            task_roles = []
            for r in removed_roles:
                task_roles.extend(_ROLE_TO_TASK_ROLES.get(r.lower(), []))
            task_roles = list(set(task_roles))
            if task_roles:
                pt_res = (
                    db.table("tasks")
                    .select("task_id", count="exact")
                    .eq("tenant_id", tenant_id)
                    .eq("property_id", property_id)
                    .eq("assigned_to", user_id)
                    .eq("status", "PENDING")
                    .gte("due_date", today)
                    .execute()
                )
                pending_count = pt_res.count or len(pt_res.data or [])

        # 4. Count ACKNOWLEDGED tasks that will NOT auto-move
        ack_count = 0
        ack_res = (
            db.table("tasks")
            .select("task_id", count="exact")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("assigned_to", user_id)
            .eq("status", "ACKNOWLEDGED")
            .gte("due_date", today)
            .execute()
        )
        ack_count = ack_res.count or len(ack_res.data or [])

        return JSONResponse(status_code=200, content={
            "user_id":             user_id,
            "property_id":         property_id,
            "removed_name":        removed_name,
            "is_primary":          is_primary,
            "new_primary_user_id": next_backup,
            "new_primary_name":    new_primary_name,
            "pending_tasks_count": pending_count,
            "acknowledged_tasks_count": ack_count,
            "summary": (
                f"Removing {removed_name} (Primary). {new_primary_name} will be promoted. "
                f"{pending_count} PENDING task(s) will transfer. {ack_count} ACKNOWLEDGED task(s) require manual action."
            ) if is_primary else (
                f"Removing {removed_name} (Backup). No baton transfer needed. "
                f"Primary worker continues unchanged."
            ),
        })
    except Exception as exc:
        logger.exception("GET /staff/assignments/%s/%s/removal-preview error: %s", user_id, property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 1030 — New endpoint: list all workers for a property with their
# priority/Primary/Backup status (used by the staff card property section)
# ---------------------------------------------------------------------------

@router.get(
    "/staff/property-lane/{property_id}",
    tags=["staff"],
    summary="List all workers assigned to a property with their priority/lane status (Phase 1030)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_lane_workers(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """Returns all workers assigned to a property, grouped by work lane, with Primary/Backup designation."""
    try:
        db = client if client is not None else _get_supabase_client()

        # Get all assignments for this property, ordered by priority
        spa_res = (
            db.table("staff_property_assignments")
            .select("user_id, priority, assigned_at")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("priority", desc=False)
            .execute()
        )
        rows = spa_res.data or []
        if not rows:
            return JSONResponse(status_code=200, content={"property_id": property_id, "lanes": {}})

        user_ids = [r["user_id"] for r in rows]
        perm_res = (
            db.table("tenant_permissions")
            .select("user_id, display_name, role, worker_roles, photo_url, is_active")
            .eq("tenant_id", tenant_id)
            .in_("user_id", user_ids)
            .execute()
        )
        perm_map = {p["user_id"]: p for p in (perm_res.data or [])}

        _SUPERVISORY_ROLES = {"manager", "admin", "owner"}

        # Lane classification (workers only)
        def _lane(roles: list) -> str:
            if not roles:
                return "unassigned"
            r = [x.lower() for x in roles]
            if "cleaner" in r:
                return "cleaning"
            if "checkin" in r or "checkout" in r:
                return "checkin_checkout"
            if "maintenance" in r:
                return "maintenance"
            return "other"

        lanes: dict = {}
        # Phase 1038: Supervisory users (manager/admin/owner) are returned separately.
        # They do not participate in worker lanes and must not appear in the lane stack.
        supervisors: list = []

        for spa_row in rows:
            uid = spa_row["user_id"]
            perm = perm_map.get(uid, {})
            sys_role = perm.get("role", "worker")
            worker_roles = perm.get("worker_roles") or []

            if sys_role in _SUPERVISORY_ROLES:
                # Supervisory-scope assignment — goes into supervisors[], not lanes
                supervisors.append({
                    "user_id":      uid,
                    "display_name": perm.get("display_name", uid),
                    "photo_url":    perm.get("photo_url"),
                    "role":         sys_role,
                    "is_active":    perm.get("is_active", True),
                    "assigned_at":  spa_row.get("assigned_at"),
                })
            else:
                lane = _lane(worker_roles)
                if lane not in lanes:
                    lanes[lane] = []
                priority = spa_row.get("priority", 1)
                lanes[lane].append({
                    "user_id":      uid,
                    "display_name": perm.get("display_name", uid),
                    "photo_url":    perm.get("photo_url"),
                    "worker_roles": worker_roles,
                    "priority":     priority,
                    "is_primary":   priority == 1,
                    "label":        "Primary" if priority == 1 else f"Backup {priority - 1}",
                    "is_active":    perm.get("is_active", True),
                    "assigned_at":  spa_row.get("assigned_at"),
                })

        return JSONResponse(status_code=200, content={
            "property_id": property_id,
            "lanes":       lanes,
            "supervisors": supervisors,   # Phase 1038: manager/admin/owner assigned to this property
        })
    except Exception as exc:
        logger.exception("GET /staff/property-lane/%s error: %s", property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 1030 — Helper: execute baton-transfer when a primary is removed
# ---------------------------------------------------------------------------

def _execute_baton_transfer(
    db: Any,
    tenant_id: str,
    removed_user_id: str,
    property_id: str,
) -> dict:
    """Phase 1030: When the Primary is removed from a property:
    1. Find the next backup (lowest priority != removed_user_id)
    2. Promote them to priority=1
    3. Reassign all future PENDING tasks from removed → new primary
    4. Return transfer summary

    DOES NOT touch ACKNOWLEDGED or IN_PROGRESS tasks.
    """
    from datetime import date
    today = date.today().isoformat()

    try:
        # 1. Find removed worker's roles (needed to find a lane-matching backup)
        perm_res = (
            db.table("tenant_permissions")
            .select("worker_roles")
            .eq("tenant_id", tenant_id)
            .eq("user_id", removed_user_id)
            .limit(1)
            .execute()
        )
        removed_roles = set((perm_res.data or [{}])[0].get("worker_roles") or [])

        # 2. Find the next backup: lowest priority among remaining workers on this property
        #    who share at least one worker_role with the removed Primary (lane-aware).
        #
        #    Phase 1030-fix: The original code picked ANY worker by lowest priority,
        #    which meant a Cleaner or Maintenance worker could "replace" a removed
        #    Check-in Primary, leaving the real Check-in Backup (e.g. Mandy) unpromoted.
        #    Now we fetch all remaining workers, join their roles, and select the correct one.
        all_remaining = (
            db.table("staff_property_assignments")
            .select("user_id, priority")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .neq("user_id", removed_user_id)
            .order("priority", desc=False)
            .limit(50)
            .execute()
        )
        if not (all_remaining.data or []):
            return {"transfer_occurred": False, "reason": "no_backup_available",
                    "new_primary_user_id": None, "tasks_transferred": 0}

        # Fetch roles for all candidates in one query
        candidate_ids = [r["user_id"] for r in all_remaining.data]
        roles_res = (
            db.table("tenant_permissions")
            .select("user_id, worker_roles")
            .eq("tenant_id", tenant_id)
            .in_("user_id", candidate_ids)
            .execute()
        )
        roles_by_user = {
            r["user_id"]: set(r.get("worker_roles") or [])
            for r in (roles_res.data or [])
        }

        # Pick the candidate with lowest priority whose roles overlap with the removed worker's lane
        new_primary_id = None
        for candidate in all_remaining.data:
            uid = candidate["user_id"]
            candidate_roles = roles_by_user.get(uid, set())
            if removed_roles and candidate_roles & removed_roles:
                # At least one role in common — correct lane match
                new_primary_id = uid
                break

        if new_primary_id is None:
            return {"transfer_occurred": False, "reason": "no_lane_matching_backup",
                    "new_primary_user_id": None, "tasks_transferred": 0}

        # 3. Promote new primary to priority=1
        now = datetime.now(tz=timezone.utc).isoformat()
        db.table("staff_property_assignments").update({
            "priority": 1,
        }).eq("tenant_id", tenant_id).eq("user_id", new_primary_id).eq("property_id", property_id).execute()

        # 4. Map roles to task worker_role values
        task_roles: list = []
        for r in removed_roles:
            task_roles.extend(_ROLE_TO_TASK_ROLES.get(r.lower(), []))
        task_roles = list(set(task_roles))

        if not task_roles:
            return {"transfer_occurred": True, "new_primary_user_id": new_primary_id,
                    "tasks_transferred": 0, "reason": "no_matching_task_roles"}

        # 5. Reassign future PENDING tasks from removed → new primary
        task_res = (
            db.table("tasks")
            .select("task_id")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("assigned_to", removed_user_id)
            .eq("status", "PENDING")
            .gte("due_date", today)
            .in_("worker_role", task_roles)
            .limit(200)
            .execute()
        )
        task_ids = [t["task_id"] for t in (task_res.data or [])]

        if task_ids:
            db.table("tasks").update({
                "assigned_to": new_primary_id,
                "updated_at": now,
            }).in_("task_id", task_ids).eq("status", "PENDING").eq("assigned_to", removed_user_id).execute()

        # 6. Write audit log for the baton-transfer event
        try:
            from services.audit_writer import write_audit_event
            write_audit_event(
                db, tenant_id=tenant_id, entity_type="staff_baton_transfer",
                entity_id=property_id, action="baton_transfer",
                details={
                    "removed_primary": removed_user_id,
                    "new_primary": new_primary_id,
                    "property_id": property_id,
                    "tasks_transferred": len(task_ids),
                    "task_ids": task_ids[:20],
                    "note": "ACKNOWLEDGED and IN_PROGRESS tasks were NOT moved automatically.",
                }
            )
        except Exception:
            pass

        # 7. Record promotion in comm_preference for login-banner display.
        # Phase 1030-fix: The original code called db.rpc("update_promotion_notice", ...)
        # which silently failed because that RPC function was never created in the DB.
        # Replaced with a direct read-modify-write on tenant_permissions.comm_preference JSONB.
        # The worker app checks comm_preference._promotion_notice on login,
        # shows the banner, then clears it via PATCH /profile.
        try:
            pref_res = (
                db.table("tenant_permissions")
                .select("comm_preference")
                .eq("tenant_id", tenant_id)
                .eq("user_id", new_primary_id)
                .limit(1)
                .execute()
            )
            existing_pref = (pref_res.data or [{}])[0].get("comm_preference") or {}
            existing_pref["_promotion_notice"] = {
                "property_id": property_id,
                "tasks_transferred": len(task_ids),
                "promoted_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            db.table("tenant_permissions").update({
                "comm_preference": existing_pref,
            }).eq("tenant_id", tenant_id).eq("user_id", new_primary_id).execute()
            logger.info(
                "baton_transfer: promotion_notice written for new_primary=%s property=%s",
                new_primary_id, property_id,
            )
        except Exception as _pn_exc:
            # Promotion notice is best-effort — must not fail the transfer.
            # But we log it explicitly so ops can see when awareness breaks.
            logger.warning(
                "baton_transfer: failed to write promotion_notice for %s/%s: %s",
                new_primary_id, property_id, _pn_exc,
            )
            pass

        logger.info(
            "baton_transfer: removed=%s new_primary=%s property=%s tasks_transferred=%d",
            removed_user_id, new_primary_id, property_id, len(task_ids),
        )

        return {
            "transfer_occurred": True,
            "new_primary_user_id": new_primary_id,
            "tasks_transferred": len(task_ids),
            "task_ids": task_ids[:20],
        }

    except Exception as exc:
        logger.warning("baton_transfer: failed for %s/%s: %s", removed_user_id, property_id, exc)
        return {"transfer_occurred": False, "error": str(exc), "tasks_transferred": 0}
