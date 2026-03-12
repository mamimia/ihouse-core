"""
Owner Portal Router — Phase 298
==================================

JWT-protected endpoints for property owners.
Access is scoped to properties granted via owner_portal_access table.

Endpoints:
    GET  /owner/portal              — List properties the owner can see
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
    summary="List owner's accessible properties (Phase 298)",
    tags=["owner-portal"],
)
async def list_owner_properties(
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /owner/portal

    Returns all properties the caller (as an owner) is allowed to see.
    Includes the caller's role for each property (owner | viewer).
    """
    db = _get_db()
    properties = get_owner_properties(db, owner_id=caller_id)
    return JSONResponse(
        status_code=200,
        content={"properties": properties, "count": len(properties)},
    )


@router.get(
    "/owner/portal/{property_id}/summary",
    summary="Get property summary for owner (Phase 298)",
    tags=["owner-portal"],
)
async def get_property_summary(
    property_id: str,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /owner/portal/{property_id}/summary

    Returns a summary of a specific property the owner has access to.
    Requires caller to have active owner_portal_access for this property_id.

    Note: Uses DB metadata query. Financial details shown only for 'owner' role.
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

    # Query the booking_state projection for summary data
    try:
        res = (
            db.table("booking_state")
            .select("booking_ref, check_in_date, check_out_date, status, gross_revenue")
            .eq("property_id", property_id)
            .order("check_in_date", desc=True)
            .limit(10)
            .execute()
        )
        bookings = res.data or []
    except Exception:
        bookings = []

    summary: dict = {
        "property_id": property_id,
        "role": role,
        "recent_bookings_count": len(bookings),
    }

    # Show financial summary only for 'owner' role
    if role == "owner" and bookings:
        revenues = [b.get("gross_revenue", 0) or 0 for b in bookings]
        summary["total_recent_revenue"] = sum(revenues)

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
