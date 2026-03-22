"""
Phase 862 P16 — Submitter / My Properties Router
==================================================

Backend endpoints for the My Properties page.

GET  /properties/mine          — list intake requests + properties for the authenticated user
POST /properties/{id}/submit   — submit a draft intake for admin review
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

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


def _extract_user_id(request: Request, fallback_tenant_id: str) -> str:
    """Extract user_id from JWT claims (sub). Falls back to tenant_id from jwt_auth."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from api.auth import decode_jwt_claims
            raw_token = auth_header[7:].strip()
            jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
            if jwt_secret and raw_token:
                claims = decode_jwt_claims(raw_token, jwt_secret)
                sub = claims.get("sub", "")
                if sub:
                    return sub
        except Exception:
            pass
    return fallback_tenant_id


@router.get(
    "/properties/mine",
    tags=["submitter"],
    summary="List my submitted properties and intake requests (Phase 862 P16)",
    responses={
        200: {"description": "List of user's properties and intake requests"},
        403: {"description": "Not authenticated"},
    },
)
async def list_my_properties(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P16: Returns all intake_requests and properties belonging to the authenticated user.

    Intake requests are matched by user_id (from Phase 862 P14 linkage).
    Properties are matched by submitted_by or owner_id fields if they exist.
    """
    user_id = _extract_user_id(request, tenant_id)
    items = []

    db = _get_db()
    if not db:
        return ok({"items": [], "count": 0})

    # 1. Fetch intake_requests linked to this user
    try:
        intake_result = (
            db.table("intake_requests")
            .select("id, reference_id, name, email, company, portfolio_size, status, source, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        for row in (intake_result.data or []):
            items.append({
                "id": row.get("id"),
                "reference_id": row.get("reference_id"),
                "name": row.get("name", ""),
                "type": "intake_request",
                "status": row.get("status", "pending_review"),
                "submitted_at": row.get("created_at"),
                "details": {
                    "email": row.get("email"),
                    "company": row.get("company"),
                    "portfolio_size": row.get("portfolio_size"),
                    "source": row.get("source"),
                },
            })
    except Exception as exc:
        logger.warning("properties/mine: intake lookup failed for user=%s: %s", user_id, exc)

    # 2. Fetch properties submitted directly by this user via the onboard flow
    # These are written to the properties table with submitter_user_id by /api/onboard.
    try:
        prop_result = (
            db.table("properties")
            .select("property_id, display_name, property_type, city, country, status, created_at, max_guests, bedrooms, submitter_user_id, submitter_email")
            .eq("submitter_user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        seen_ids = {item.get("id") for item in items}
        for row in (prop_result.data or []):
            prop_id = row.get("property_id")
            if prop_id in seen_ids:
                continue
            seen_ids.add(prop_id)
            items.append({
                "id": prop_id,
                "reference_id": prop_id,
                "name": row.get("display_name", ""),
                "property_type": row.get("property_type", ""),
                "city": row.get("city", ""),
                "country": row.get("country", ""),
                "max_guests": row.get("max_guests"),
                "bedrooms": row.get("bedrooms"),
                "type": "property",
                "status": row.get("status", "draft"),
                "submitted_at": row.get("created_at"),
            })
    except Exception as exc:
        logger.warning("properties/mine: property lookup failed for user=%s: %s", user_id, exc)

    # Sort all items by submitted_at descending
    items.sort(key=lambda x: x.get("submitted_at") or "", reverse=True)

    return ok({"items": items, "count": len(items)})


@router.get(
    "/properties/{property_id}/draft",
    tags=["submitter"],
    summary="Get a draft property by ID to edit before submission",
)
async def get_draft_property(
    property_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    user_id = _extract_user_id(request, tenant_id)
    db = _get_db()
    if not db: return ok({"error": "db not configured"})
    result = db.table("properties").select("*").eq("property_id", property_id).eq("submitter_user_id", user_id).limit(1).execute()
    if not result.data:
        return err("NOT_FOUND", "Draft not found or unauthorized", 404)
    # fetch photos
    try:
        photos_res = db.table("property_photos").select("photo_url").eq("property_id", property_id).order("sort_order").execute()
        result.data[0]["photos"] = [p["photo_url"] for p in photos_res.data]
    except Exception as exc:
        result.data[0]["photos"] = []
        logger.warning(f"Error fetching photos: {exc}")
    return ok(result.data[0])

@router.put(
    "/properties/{property_id}/draft",
    tags=["submitter"],
    summary="Update a draft property before submission",
)
async def update_draft_property(
    property_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    user_id = _extract_user_id(request, tenant_id)
    db = _get_db()
    if not db: return ok({"error": "db not configured"})
    check = db.table("properties").select("status").eq("property_id", property_id).eq("submitter_user_id", user_id).limit(1).execute()
    if not check.data or check.data[0].get("status") != "draft":
        return err("NOT_FOUND", "Cannot edit non-draft property", 400)
    
    body = await request.json()
    
    # Extract photos to save to property_photos
    photos = body.pop("photos", None)
    
    try:
        db.table("properties").update(body).eq("property_id", property_id).eq("submitter_user_id", user_id).execute()
    except Exception as exc:
        return err("UPDATE_FAILED", f"Failed to update: {exc}", 500)
    
    if photos is not None and isinstance(photos, list):
        try:
            db.table("property_photos").delete().eq("property_id", property_id).execute()
            for i, phot_url in enumerate(photos):
                db.table("property_photos").insert({
                    "tenant_id": "DOM-ONB-000",
                    "property_id": property_id,
                    "photo_url": phot_url,
                    "room_type": "general",
                    "sort_order": i,
                    "is_hero": i == 0
                }).execute()
        except Exception as e:
            logger.error("Failed to update photos: %s", e)
            
    return ok({"property_id": property_id, "updated": True})

@router.post(
    "/properties/{intake_id}/submit",
    tags=["submitter"],
    summary="Submit a draft intake request for admin review (Phase 862 P16)",
    responses={
        200: {"description": "Intake request submitted for review"},
        403: {"description": "Not authenticated or not the submitter"},
        404: {"description": "Intake request not found"},
    },
)
async def submit_intake_for_review(
    intake_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P16: Transitions an intake request from 'draft' to 'pending_review'.

    Only the original submitter (matched by user_id) can submit their own drafts.
    """
    user_id = _extract_user_id(request, tenant_id)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    # First try intake_requests table (legacy path)
    try:
        result = (
            db.table("intake_requests")
            .select("id, user_id, status")
            .eq("id", intake_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if rows:
            row = rows[0]
            if row.get("user_id") != user_id:
                return err("FORBIDDEN", "You can only submit your own intake requests.", status=403)
            current_status = row.get("status", "")
            if current_status not in ("draft", "pending_review"):
                return err("INVALID_STATE", f"Cannot submit: current status is '{current_status}'.", status=400)
            db.table("intake_requests").update({"status": "pending_review"}).eq("id", intake_id).execute()
            logger.info("properties/submit: intake %s submitted for review by user=%s", intake_id, user_id)
            return ok({"intake_id": intake_id, "status": "pending_review"})
    except Exception as exc:
        logger.warning("properties/submit: intake lookup failed for %s: %s", intake_id, exc)

    # Fall back to properties table (onboard path — property_id like DOM-018)
    try:
        prop_result = (
            db.table("properties")
            .select("property_id, submitter_user_id, status")
            .eq("property_id", intake_id)
            .limit(1)
            .execute()
        )
        prop_rows = prop_result.data or []
        if not prop_rows:
            return err("NOT_FOUND", f"Property {intake_id} not found.", status=404)

        prop = prop_rows[0]
        submitter = str(prop.get("submitter_user_id") or "")
        if submitter != user_id:
            return err("FORBIDDEN", "You can only submit your own properties.", status=403)

        current_status = prop.get("status", "")
        if current_status not in ("draft", "pending_review"):
            return err("INVALID_STATE", f"Cannot submit: current status is '{current_status}'.", status=400)

        db.table("properties").update({"status": "pending_review"}).eq("property_id", intake_id).execute()
        logger.info("properties/submit: property %s submitted for review by user=%s", intake_id, user_id)
        return ok({"intake_id": intake_id, "property_id": intake_id, "status": "pending_review"})

    except Exception as exc:
        logger.warning("properties/submit: property lookup failed for %s user=%s: %s", intake_id, user_id, exc)
        return err("SUBMIT_FAILED", str(exc), status=500)


# ---------------------------------------------------------------------------
# Phase 862 P25: Admin intake approval / rejection endpoints
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field


class ApproveRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant to provision the owner into")
    property_ids: list[str] = Field(
        default=[],
        description="Optional property IDs to auto-grant owner_portal_access (Phase 862 P35)",
    )


@router.post(
    "/admin/intake/{intake_id}/approve",
    tags=["admin", "submitter"],
    summary="Approve an intake request and provision owner (Phase 862 P25)",
    responses={
        200: {"description": "Intake approved and owner provisioned"},
        403: {"description": "Admin role required"},
        404: {"description": "Intake request not found"},
    },
)
async def admin_approve_intake(
    intake_id: str,
    body: ApproveRequest,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P25: Admin-only endpoint to approve an intake request.
    Calls approve_intake() from the submitter state machine.
    """
    # Verify admin role
    admin_user_id = _extract_user_id(request, tenant_id)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from api.auth import decode_jwt_claims
        raw_token = auth_header[7:].strip()
        jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
        if jwt_secret:
            claims = decode_jwt_claims(raw_token, jwt_secret)
            role = claims.get("role", "")
            if role not in ("admin", "manager"):
                return err("ADMIN_REQUIRED", "Only admin/manager can approve intake requests.", status=403)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        from services.submitter_states import approve_intake
        result = approve_intake(
            db, intake_id,
            admin_user_id=admin_user_id,
            tenant_id=body.tenant_id,
        )

        # Phase 862 P35: auto-grant owner_portal_access for specified properties
        granted_properties = []
        if body.property_ids and result.get("user_id"):
            from services.guest_token import grant_owner_access
            owner_user_id = result["user_id"]
            for prop_id in body.property_ids:
                try:
                    grant_owner_access(
                        db,
                        grantor_tenant_id=body.tenant_id,
                        owner_id=owner_user_id,
                        property_id=prop_id,
                        role="owner",
                    )
                    granted_properties.append(prop_id)
                    logger.info(
                        "admin/intake/approve: granted owner_portal_access for property=%s to user=%s",
                        prop_id, owner_user_id,
                    )
                except ValueError as exc:
                    logger.warning(
                        "admin/intake/approve: property grant skipped for %s: %s",
                        prop_id, exc,
                    )
            result["granted_properties"] = granted_properties

        logger.info(
            "admin/intake/approve: intake=%s approved by admin=%s -> tenant=%s properties=%s",
            intake_id, admin_user_id, body.tenant_id, granted_properties,
        )
        return ok(result)
    except ValueError as exc:
        return err("APPROVAL_FAILED", str(exc), status=400)
    except RuntimeError as exc:
        return err("PROVISION_FAILED", str(exc), status=500)


@router.post(
    "/admin/intake/{intake_id}/reject",
    tags=["admin", "submitter"],
    summary="Reject an intake request (Phase 862 P25)",
    responses={
        200: {"description": "Intake request rejected"},
        403: {"description": "Admin role required"},
        404: {"description": "Intake request not found"},
    },
)
async def admin_reject_intake(
    intake_id: str,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P25: Admin-only endpoint to reject an intake request.
    """
    admin_user_id = _extract_user_id(request, tenant_id)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        from api.auth import decode_jwt_claims
        raw_token = auth_header[7:].strip()
        jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
        if jwt_secret:
            claims = decode_jwt_claims(raw_token, jwt_secret)
            role = claims.get("role", "")
            if role not in ("admin", "manager"):
                return err("ADMIN_REQUIRED", "Only admin/manager can reject intake requests.", status=403)

    db = _get_db()
    if not db:
        return err("DB_NOT_CONFIGURED", "Database not available.", status=503)

    try:
        from services.submitter_states import transition_intake
        result = transition_intake(
            db, intake_id,
            current_status="pending_review",
            target_status="rejected",
            admin_user_id=admin_user_id,
        )
        logger.info("admin/intake/reject: intake=%s rejected by admin=%s", intake_id, admin_user_id)
        return ok(result)
    except ValueError as exc:
        return err("REJECTION_FAILED", str(exc), status=400)
    except RuntimeError as exc:
        return err("REJECTION_FAILED", str(exc), status=500)
