"""
Owner Portal Router — Phase 298
Phase 1021-E — Owner model unification: portal identity reconciliation
==================================

JWT-protected endpoints for property owners.
Access is scoped to properties granted via owner_portal_access table.

Phase 1021-E reconciliation:
    - The owner identity for access gating remains the JWT sub (owner_portal_access.owner_id).
    - /owner/portal now also resolves the linked owner business profile from public.owners
      via owners.user_id = JWT sub. If linked, profile data (name, email, id) is returned.
    - This bridges the auth identity and the business profile without changing the access model.

Endpoints:
    GET  /owner/portal              — List properties the owner can see (+ linked profile)
    GET  /owner/portal/{property_id}/summary — Property summary + booking count
    POST /admin/owner-access        — Admin grants owner portal access to a property
    DELETE /admin/owner-access/{owner_id}/{property_id} — Admin revokes access

Design:
    - Owner identifies via JWT (tenant_id = their user ID).
    - Operators grant them property-level access via /admin/owner-access.
    - All read endpoints are scoped to the owner's allowed properties.
    - Financial data is visible only for 'owner' role (not 'viewer').
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from services.guest_token import (
    get_owner_properties,
    grant_owner_access,
    has_owner_access,
)
from services.owner_portal_data import get_owner_property_rich_summary  # Phase 301

logger = logging.getLogger(__name__)

router = APIRouter(tags=["owner-portal"])


def _get_db():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GrantOwnerAccessRequest(BaseModel):
    owner_id: str = Field(..., description="Owner's tenant_id (JWT sub)")
    property_id: str = Field(..., description="Property ID to grant access to")
    role: str = Field("owner", description="'owner' | 'viewer'")


# ---------------------------------------------------------------------------
# Owner-facing endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/owner/portal",
    summary="List owner's accessible properties (Phase 298 / 1021-E)",
    tags=["owner-portal"],
)
async def list_owner_properties(
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /owner/portal

    Returns all properties the caller (as an owner) is allowed to see.
    Includes the caller's role for each property (owner | viewer).

    Phase 1021-E: Also resolves the linked owner business profile from public.owners
    (via owners.user_id = caller_id). Returns as owner_profile (null if not linked).
    This reconciles the portal auth identity with the business profile entity.
    """
    db = _get_db()
    properties = get_owner_properties(db, owner_id=caller_id)

    # Phase 1021-E: Resolve linked owner business profile
    owner_profile = None
    try:
        profile_res = (
            db.table("owners")
            .select("id, name, email, phone, property_ids")
            .eq("user_id", caller_id)
            .maybe_single()
            .execute()
        )
        if profile_res.data:
            owner_profile = {
                "id": profile_res.data.get("id"),
                "name": profile_res.data.get("name"),
                "email": profile_res.data.get("email"),
                "phone": profile_res.data.get("phone"),
            }
    except Exception as exc:
        logger.warning("list_owner_properties: failed to resolve owner profile: %s", exc)

    return JSONResponse(
        status_code=200,
        content={
            "properties": properties,
            "count": len(properties),
            "owner_profile": owner_profile,  # null if not yet linked to a business profile
        },
    )


@router.get(
    "/owner/portal/{property_id}/summary",
    summary="Get rich property summary for owner (Phase 301)",
    tags=["owner-portal"],
)
async def get_property_summary(
    property_id: str,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /owner/portal/{property_id}/summary

    Returns a rich property summary for an authenticated owner. Requires
    active owner_portal_access for this property_id.

    Phase 301 enrichment (over Phase 298):
        - booking_counts   — breakdown by status (confirmed/cancelled/etc.)
        - upcoming_bookings — next 5 bookings with nights calculation
        - occupancy         — 30-day occupancy % from booking_state
        - financials        — 90-day totals from booking_financial_facts (owner role only)

    Financial data (net_revenue, management_fee, ota_commission) is returned
    only when the caller's role == 'owner'. Viewers see booking data only.
    """
    db = _get_db()

    if not has_owner_access(db, owner_id=caller_id, property_id=property_id):
        raise HTTPException(
            status_code=403,
            detail=f"No access to property '{property_id}'.",
        )

    # Get the role to determine financial visibility
    properties = get_owner_properties(db, owner_id=caller_id)
    role = next(
        (p["role"] for p in properties if p["property_id"] == property_id),
        "viewer",
    )

    summary = get_owner_property_rich_summary(
        db=db,
        property_id=property_id,
        role=role,
        financial_period_days=90,
        occupancy_period_days=30,
    )

    return JSONResponse(status_code=200, content=summary)


# ---------------------------------------------------------------------------
# Admin-facing endpoints (operator grants owner access)
# ---------------------------------------------------------------------------

@router.post(
    "/admin/owner-access",
    summary="Grant owner portal access to a property (Phase 298)",
    status_code=201,
    tags=["owner-portal"],
)
async def grant_access(
    body: GrantOwnerAccessRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /admin/owner-access

    Operator (caller) grants owner_id access to property_id.
    Caller must be authenticated (JWT). Any authenticated tenant can grant access.
    For tighter control, wire in org_admin checks from Phase 296.
    """
    db = _get_db()
    try:
        row = grant_owner_access(
            db=db,
            grantor_tenant_id=caller_id,
            owner_id=body.owner_id,
            property_id=body.property_id,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    logger.info(
        "owner-access: granted %s to %s for property %s by %s",
        body.role, body.owner_id, body.property_id, caller_id,
    )
    return JSONResponse(status_code=201, content={"granted": True, "access": row})


@router.delete(
    "/admin/owner-access/{owner_id}/{property_id}",
    summary="Revoke owner portal access (Phase 298)",
    tags=["owner-portal"],
)
async def revoke_access(
    owner_id: str,
    property_id: str,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    DELETE /admin/owner-access/{owner_id}/{property_id}

    Revokes the owner's access to a property (sets revoked_at).
    """
    from datetime import datetime, timezone
    db = _get_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        res = (
            db.table("owner_portal_access")
            .update({"revoked_at": now_iso})
            .eq("owner_id", owner_id)
            .eq("property_id", property_id)
            .is_("revoked_at", "null")
            .execute()
        )
        found = bool(res.data)
    except Exception as exc:
        logger.exception("revoke owner access error: %s", exc)
        found = False

    if not found:
        raise HTTPException(status_code=404, detail="Access record not found or already revoked.")

    logger.info("owner-access: revoked for %s property %s by %s", owner_id, property_id, caller_id)
    return JSONResponse(
        status_code=200,
        content={"revoked": True, "owner_id": owner_id, "property_id": property_id},
    )
