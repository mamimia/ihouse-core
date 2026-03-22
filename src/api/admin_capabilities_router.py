"""
Phase 862 P32 — Admin Capability Management Router
====================================================

Admin endpoints for managing operational manager delegated capabilities.

Endpoints:
    GET  /admin/managers                           — list all managers in the admin's tenant
    GET  /admin/managers/{user_id}/capabilities     — get capabilities for a specific manager
    PATCH /admin/managers/{user_id}/capabilities    — set/update capabilities for a manager
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from api.envelope import ok, err

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db() -> Any:
    """Get Supabase client with service_role key."""
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def _extract_admin_claims(request: Request, tenant_id_from_jwt: str) -> dict:
    """Extract and validate admin claims from JWT."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return {}
    from api.auth import decode_jwt_claims
    raw_token = auth_header[7:].strip()
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return {}
    return decode_jwt_claims(raw_token, jwt_secret)


def _is_admin(claims: dict) -> bool:
    """Check if JWT claims indicate admin or manager role."""
    return claims.get("role", "") in ("admin", "manager")


# ---------------------------------------------------------------------------
# GET /admin/managers — List all managers in the admin's tenant
# ---------------------------------------------------------------------------

@router.get(
    "/admin/managers",
    tags=["admin", "capabilities"],
    summary="List all managers in the tenant (Phase 862 P32)",
    responses={
        200: {"description": "List of managers with their capabilities"},
        403: {"description": "Admin role required"},
    },
)
async def list_managers(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P32: Returns all users with role=manager in the admin's tenant.
    Includes their current delegated capabilities.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin/manager can view managers.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        result = (
            db.table("tenant_permissions")
            .select("user_id, role, is_active, permissions")
            .eq("tenant_id", admin_tenant_id)
            .eq("role", "manager")
            .execute()
        )
        rows = result.data or []

        # Enrich with user emails from Supabase Auth
        managers = []
        for row in rows:
            user_id = row["user_id"]
            email = ""
            full_name = ""
            try:
                user_obj = db.auth.admin.get_user_by_id(user_id)
                if user_obj and user_obj.user:
                    email = user_obj.user.email or ""
                    metadata = user_obj.user.user_metadata or {}
                    full_name = metadata.get("full_name", "") or metadata.get("name", "")
            except Exception:
                pass

            from services.delegated_capabilities import get_delegated_capabilities
            caps = get_delegated_capabilities(row.get("permissions"))

            managers.append({
                "user_id": user_id,
                "email": email,
                "full_name": full_name,
                "is_active": row.get("is_active", True),
                "capabilities": caps,
            })

        return ok({"managers": managers, "count": len(managers)})
    except Exception as exc:
        logger.exception("admin/managers: failed to list: %s", exc)
        return err("LIST_FAILED", f"Failed to list managers: {exc}", status=500)


# ---------------------------------------------------------------------------
# GET /admin/managers/{user_id}/capabilities — Get manager capabilities
# ---------------------------------------------------------------------------

@router.get(
    "/admin/managers/{user_id}/capabilities",
    tags=["admin", "capabilities"],
    summary="Get capabilities for a specific manager (Phase 862 P32)",
    responses={
        200: {"description": "Manager capabilities returned"},
        403: {"description": "Admin role required"},
        404: {"description": "Manager not found"},
    },
)
async def get_manager_capabilities(
    user_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P32: Returns the delegated capabilities for a specific manager.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin/manager can view capabilities.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        result = (
            db.table("tenant_permissions")
            .select("user_id, role, permissions, is_active")
            .eq("tenant_id", admin_tenant_id)
            .eq("user_id", user_id)
            .eq("role", "manager")
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return err("NOT_FOUND", f"No manager found with user_id={user_id}", status=404)

        row = rows[0]
        from services.delegated_capabilities import get_delegated_capabilities, ALL_CAPABILITIES
        caps = get_delegated_capabilities(row.get("permissions"))

        return ok({
            "user_id": user_id,
            "is_active": row.get("is_active", True),
            "capabilities": caps,
            "available_capabilities": sorted(ALL_CAPABILITIES),
        })
    except Exception as exc:
        logger.exception("admin/managers/%s/capabilities: %s", user_id, exc)
        return err("FETCH_FAILED", f"Failed to fetch capabilities: {exc}", status=500)


# ---------------------------------------------------------------------------
# PATCH /admin/managers/{user_id}/capabilities — Set manager capabilities
# ---------------------------------------------------------------------------

class CapabilitiesUpdateRequest(BaseModel):
    capabilities: dict[str, bool] = Field(
        ...,
        description="Dict of capability_name → True/False",
        examples=[{"financial": True, "staffing": False}],
    )


@router.patch(
    "/admin/managers/{user_id}/capabilities",
    tags=["admin", "capabilities"],
    summary="Update capabilities for a manager (Phase 862 P32)",
    responses={
        200: {"description": "Capabilities updated"},
        403: {"description": "Admin role required"},
        404: {"description": "Manager not found"},
        422: {"description": "Invalid capability name"},
    },
)
async def update_manager_capabilities(
    user_id: str,
    body: CapabilitiesUpdateRequest,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P32: Admin-only endpoint to set delegated capabilities for a manager.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin/manager can set capabilities.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)
    admin_user_id = claims.get("sub", "")

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        from services.delegated_capabilities import set_capabilities
        result = set_capabilities(
            db,
            tenant_id=admin_tenant_id,
            user_id=user_id,
            capabilities=body.capabilities,
        )
        logger.info(
            "admin/managers/%s/capabilities: updated by admin=%s caps=%s",
            user_id, admin_user_id, body.capabilities,
        )
        return ok(result)
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 422
        return err("INVALID_REQUEST", str(exc), status=status)
    except Exception as exc:
        logger.exception("admin/managers/%s/capabilities: update failed: %s", user_id, exc)
        return err("UPDATE_FAILED", f"Failed to update capabilities: {exc}", status=500)
