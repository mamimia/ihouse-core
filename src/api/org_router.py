"""
Organization Admin Router — Phase 296
========================================

Provides HTTP API for multi-tenant organization management.

Endpoints:
    POST /admin/org                             — create a new org
    GET  /admin/org                             — list orgs the caller belongs to
    GET  /admin/org/{org_id}                    — get a single org (admin only)
    GET  /admin/org/{org_id}/members            — list org members (admin only)
    POST /admin/org/{org_id}/members            — invite a member (org_admin only)
    DELETE /admin/org/{org_id}/members/{tid}    — remove a member (org_admin only)

Auth:
    All endpoints require JWT Bearer (tenant_id from sub claim).
    Membership and admin checks are enforced per-endpoint.

Invariant:
    The tenant_id JWT claim is NEVER changed. The org layer is additive —
    existing booking/financial/task endpoints are unaffected.
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from services.organization import (
    create_organization,
    get_organization,
    get_org_for_tenant,
    list_orgs_for_tenant,
    add_org_member,
    list_org_members,
    remove_org_member,
    is_org_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["org"])


def _get_db():
    """Return a Supabase service-role client (same pattern as all admin routers)."""
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Organization display name")
    slug: str | None = Field(None, description="URL-safe identifier (auto-derived if omitted)")
    description: str | None = Field(None, max_length=500)


class AddMemberRequest(BaseModel):
    tenant_id: str = Field(..., description="JWT sub (tenant_id) of the user to add")
    role: str = Field("member", description="'org_admin' | 'manager' | 'member'")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/admin/org",
    summary="Create a new organization (Phase 296)",
    status_code=201,
)
async def create_org(
    body: CreateOrgRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /admin/org

    Creates a new organization and enrolls the caller as org_admin.

    - `name` is required (1-100 characters).
    - `slug` is auto-derived from name if omitted.
    - Slugs must be globally unique.

    Returns the created organization object.
    """
    db = _get_db()
    try:
        org = create_organization(
            db,
            name=body.name,
            creator_tenant_id=caller_id,
            description=body.description,
            slug=body.slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(status_code=201, content={"org": org})


@router.get(
    "/admin/org",
    summary="List organizations the caller belongs to (Phase 296)",
)
async def list_my_orgs(
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /admin/org

    Returns all organizations the caller is a member of (typically 0 or 1).
    Includes the caller's role in each org.
    """
    db = _get_db()
    orgs = list_orgs_for_tenant(db, caller_id)
    return JSONResponse(status_code=200, content={"orgs": orgs, "count": len(orgs)})


@router.get(
    "/admin/org/{org_id}",
    summary="Get organization details (Phase 296)",
)
async def get_org(
    org_id: str,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /admin/org/{org_id}

    Returns org details. Caller must be a member.
    """
    db = _get_db()
    org = get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Verify caller is a member
    members = list_org_members(db, org_id)
    member_ids = {m["tenant_id"] for m in members}
    if caller_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    return JSONResponse(status_code=200, content={"org": org})


@router.get(
    "/admin/org/{org_id}/members",
    summary="List org members (Phase 296)",
)
async def get_members(
    org_id: str,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /admin/org/{org_id}/members

    Returns all members of an organization. Caller must be a member.
    """
    db = _get_db()
    org = get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    members = list_org_members(db, org_id)
    member_ids = {m["tenant_id"] for m in members}
    if caller_id not in member_ids:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    return JSONResponse(status_code=200, content={"members": members, "count": len(members)})


@router.post(
    "/admin/org/{org_id}/members",
    summary="Add a member to an org (org_admin only) (Phase 296)",
    status_code=201,
)
async def add_member(
    org_id: str,
    body: AddMemberRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /admin/org/{org_id}/members

    Adds a new member to the organization. Caller must be org_admin.
    """
    db = _get_db()
    org = get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not is_org_admin(db, org_id, caller_id):
        raise HTTPException(status_code=403, detail="Only org_admin can add members")

    try:
        member = add_org_member(
            db,
            org_id=org_id,
            new_tenant_id=body.tenant_id,
            role=body.role,
            invited_by=caller_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return JSONResponse(status_code=201, content={"member": member})


@router.delete(
    "/admin/org/{org_id}/members/{tenant_id}",
    summary="Remove a member from an org (org_admin only) (Phase 296)",
)
async def remove_member(
    org_id: str,
    tenant_id: str,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    DELETE /admin/org/{org_id}/members/{tenant_id}

    Removes a member from the organization. Caller must be org_admin.
    An org_admin cannot remove themselves if they are the last admin.
    """
    db = _get_db()
    org = get_organization(db, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not is_org_admin(db, org_id, caller_id):
        raise HTTPException(status_code=403, detail="Only org_admin can remove members")

    # Safety guard: prevent removing the last org_admin
    if tenant_id == caller_id:
        members = list_org_members(db, org_id)
        admins = [m for m in members if m["role"] == "org_admin"]
        if len(admins) <= 1:
            raise HTTPException(
                status_code=422,
                detail="Cannot remove the last org_admin. Promote another member first.",
            )

    removed = remove_org_member(db, org_id, tenant_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found in this organization")

    return JSONResponse(status_code=200, content={"removed": True, "tenant_id": tenant_id})
