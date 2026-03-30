"""
Phase 1023 — Admin Capability Management Router (extended from Phase 862 P32)
==============================================================================

Admin endpoints for managing operational manager delegated capabilities.

Endpoints:
    GET  /admin/managers                                — list all managers in tenant
    GET  /admin/managers/{user_id}/capabilities         — get full grouped capabilities + taxonomy
    PATCH /admin/managers/{user_id}/capabilities        — bulk update (legacy, kept for compat)
    PATCH /admin/managers/{user_id}/capabilities/section — section-level atomic update (Phase 1023)
    GET  /admin/managers/{user_id}/capabilities/history — last N capability audit events
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
    """Only true admins can manage capabilities. Manager self-delegation is not permitted."""
    return claims.get("role", "") == "admin"


# ---------------------------------------------------------------------------
# GET /admin/managers — List all managers in the admin's tenant
# ---------------------------------------------------------------------------

@router.get(
    "/admin/managers",
    tags=["admin", "capabilities"],
    summary="List all managers in the tenant (Phase 862/1023)",
)
async def list_managers(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Returns all users with role=manager in the admin's tenant.
    Includes their current delegated capabilities.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin can view managers.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        result = (
            db.table("tenant_permissions")
            .select("user_id, role, permissions, display_name")
            .eq("tenant_id", admin_tenant_id)
            .eq("role", "manager")
            .execute()
        )
        rows = result.data or []

        from services.delegated_capabilities import get_delegated_capabilities
        managers = []
        for row in rows:
            user_id = row["user_id"]

            # Best-effort: fetch email from Supabase Auth
            email = ""
            try:
                user_obj = db.auth.admin.get_user_by_id(user_id)
                if user_obj and user_obj.user:
                    email = user_obj.user.email or ""
            except Exception:
                pass

            caps = get_delegated_capabilities(row.get("permissions"))
            managers.append({
                "user_id": user_id,
                "display_name": row.get("display_name", ""),
                "email": email,
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
    summary="Get full grouped capabilities for a manager (Phase 1023)",
)
async def get_manager_capabilities(
    user_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Returns the delegated capabilities for a specific manager,
    grouped by section with full taxonomy (for the Admin UI Delegated Authority tab).
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin can view capabilities.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        result = (
            db.table("tenant_permissions")
            .select("user_id, role, permissions")
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
        from services.delegated_capabilities import (
            get_delegated_capabilities,
            get_grouped_capabilities,
            ALL_CAPABILITIES,
            CAPABILITY_GROUPS,
        )
        caps = get_delegated_capabilities(row.get("permissions"))
        grouped = get_grouped_capabilities(row.get("permissions"))

        return ok({
            "user_id": user_id,
            "capabilities": caps,
            "grouped_capabilities": grouped,
            "available_capabilities": sorted(ALL_CAPABILITIES),
            "capability_groups": [
                {"group": g["group"], "label": g["label"]}
                for g in CAPABILITY_GROUPS
            ],
        })
    except Exception as exc:
        logger.exception("admin/managers/%s/capabilities: %s", user_id, exc)
        return err("FETCH_FAILED", f"Failed to fetch capabilities: {exc}", status=500)


# ---------------------------------------------------------------------------
# PATCH /admin/managers/{user_id}/capabilities/section — Section-level atomic update
# (Phase 1023 — preferred write path from Admin UI)
# ---------------------------------------------------------------------------

class SectionCapabilitiesRequest(BaseModel):
    section: str = Field(
        ...,
        description="Section group key (e.g. 'booking_exceptions')",
        examples=["booking_exceptions"],
    )
    capabilities: dict[str, bool] = Field(
        ...,
        description="Dict of capability_key → True/False for this section",
        examples=[{"booking_approve_early_co": True, "booking_flag_vip": False}],
    )


@router.patch(
    "/admin/managers/{user_id}/capabilities/section",
    tags=["admin", "capabilities"],
    summary="Atomically update one section of capabilities for a manager (Phase 1023)",
)
async def update_manager_capabilities_section(
    user_id: str,
    body: SectionCapabilitiesRequest,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 1023: Admin-only endpoint to atomically update one capability section.
    Writes audit_events rows for each changed capability.
    Only accepts keys belonging to the named section; extras are rejected.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin can set capabilities.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)
    admin_user_id = claims.get("sub", "")

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        from services.delegated_capabilities import set_section_capabilities
        result = set_section_capabilities(
            db=db,
            tenant_id=admin_tenant_id,
            user_id=user_id,
            section=body.section,
            capabilities=body.capabilities,
            admin_user_id=admin_user_id,
        )
        logger.info(
            "admin/managers/%s/capabilities/section: admin=%s section=%s audit_written=%s",
            user_id, admin_user_id, body.section, result.get("audit_events_written", 0),
        )
        return ok({
            "section": body.section,
            "capabilities": result["capabilities"],
            "audit_events_written": result.get("audit_events_written", 0),
        })
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 422
        return err("INVALID_REQUEST", str(exc), status=status)
    except Exception as exc:
        logger.exception("admin/managers/%s/capabilities/section: failed: %s", user_id, exc)
        return err("UPDATE_FAILED", f"Failed to update capabilities: {exc}", status=500)


# ---------------------------------------------------------------------------
# PATCH /admin/managers/{user_id}/capabilities — Bulk update (legacy compat)
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
    summary="Bulk update capabilities for a manager (Phase 862 compat)",
)
async def update_manager_capabilities(
    user_id: str,
    body: CapabilitiesUpdateRequest,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 legacy: bulk update capabilities.
    Phase 1023 UI uses the /section endpoint instead.
    Retained for backward compatibility with any existing integrations.
    Now writes audit_events rows.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin can set capabilities.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)
    admin_user_id = claims.get("sub", "")

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        from services.delegated_capabilities import set_capabilities
        result = set_capabilities(
            db=db,
            tenant_id=admin_tenant_id,
            user_id=user_id,
            capabilities=body.capabilities,
            admin_user_id=admin_user_id,
            write_audit=True,
        )
        logger.info(
            "admin/managers/%s/capabilities: updated by admin=%s audit_written=%s",
            user_id, admin_user_id, result.get("audit_events_written", 0),
        )
        return ok(result)
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 422
        return err("INVALID_REQUEST", str(exc), status=status)
    except Exception as exc:
        logger.exception("admin/managers/%s/capabilities: update failed: %s", user_id, exc)
        return err("UPDATE_FAILED", f"Failed to update capabilities: {exc}", status=500)


# ---------------------------------------------------------------------------
# GET /admin/managers/{user_id}/capabilities/history — Audit history
# ---------------------------------------------------------------------------

@router.get(
    "/admin/managers/{user_id}/capabilities/history",
    tags=["admin", "capabilities"],
    summary="Get capability change history for a manager (Phase 1023)",
)
async def get_manager_capabilities_history(
    user_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    limit: int = 20,
) -> JSONResponse:
    """
    Returns the last N audit_events for this manager where action starts
    with MANAGER_CAPABILITY_. Used by the Delegated Authority tab footer.
    """
    claims = _extract_admin_claims(request, tenant_id)
    if not _is_admin(claims):
        return err("ADMIN_REQUIRED", "Only admin can view capability history.", status=403)

    admin_tenant_id = claims.get("tenant_id", tenant_id)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        result = (
            db.table("audit_events")
            .select("id, action, actor_id, entity_id, payload, occurred_at")
            .eq("tenant_id", admin_tenant_id)
            .eq("entity_type", "manager_permission")
            .eq("entity_id", user_id)
            .in_("action", [
                "MANAGER_CAPABILITY_GRANTED",
                "MANAGER_CAPABILITY_REVOKED",
                "MANAGER_CAPABILITY_SCOPED",
            ])
            .order("occurred_at", desc=True)
            .limit(min(limit, 100))
            .execute()
        )
        events = result.data or []
        return ok({"events": events, "count": len(events)})
    except Exception as exc:
        logger.exception("admin/managers/%s/capabilities/history: %s", user_id, exc)
        return err("FETCH_FAILED", f"Failed to fetch history: {exc}", status=500)
