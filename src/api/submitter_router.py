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

    return ok({"items": items, "count": len(items)})


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

    # Look up the intake request
    try:
        result = (
            db.table("intake_requests")
            .select("id, user_id, status")
            .eq("id", intake_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return err("NOT_FOUND", f"Intake request {intake_id} not found.", status=404)

        row = rows[0]

        # Verify submitter owns this request
        if row.get("user_id") != user_id:
            return err("FORBIDDEN", "You can only submit your own intake requests.", status=403)

        # Verify status allows transition
        current_status = row.get("status", "")
        if current_status not in ("draft", "pending_review"):
            return err("INVALID_STATE", f"Cannot submit: current status is '{current_status}'.", status=400)

        # Update status
        db.table("intake_requests").update({
            "status": "pending_review",
        }).eq("id", intake_id).execute()

        logger.info("properties/submit: intake %s submitted for review by user=%s", intake_id, user_id)
        return ok({"intake_id": intake_id, "status": "pending_review"})

    except Exception as exc:
        logger.warning("properties/submit: failed for intake=%s user=%s: %s", intake_id, user_id, exc)
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
