"""
Invite Flow Router — Phase 401
=================================

Staff invitation endpoints using the access token system (Phase 399).

Endpoints:
    POST /admin/invites                 — Create an invitation (admin-only)
    GET  /invite/validate/{token}       — Public: validate invite token
    POST /invite/accept/{token}         — Public: accept invitation (one-use)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from services.access_token_service import (
    TokenType,
    issue_access_token,
    record_token,
    verify_access_token,
    validate_and_consume,
    _hash_token,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class CreateInviteRequest(BaseModel):
    email: str = Field(..., description="Email of the person being invited")
    role: str = Field(..., description="Role to assign (e.g. 'worker', 'manager', 'owner')")
    organization_name: str = Field("Domaniqo", description="Organization name to display")
    ttl_days: int = Field(7, ge=1, le=30, description="Invitation validity in days")


# ---------------------------------------------------------------------------
# Admin endpoint (JWT required)
# ---------------------------------------------------------------------------

@router.post(
    "/admin/invites",
    tags=["admin"],
    summary="Create a staff invitation (Phase 401)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_invite(
    body: CreateInviteRequest,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    POST /admin/invites

    Creates an invite token and stores metadata (role, org name, inviter).
    Returns the raw token (one-time) and a ready-to-share invite URL.
    """
    try:
        raw_token, exp = issue_access_token(
            token_type=TokenType.INVITE,
            entity_id=tenant_id,
            email=body.email,
            ttl_seconds=body.ttl_days * 86_400,
        )
    except RuntimeError as exc:
        return JSONResponse(status_code=503, content={"error": "TOKEN_SECRET_NOT_SET", "message": str(exc)})

    # Record in DB with metadata
    db = _get_db()
    record = record_token(
        tenant_id=tenant_id,
        token_type=TokenType.INVITE,
        entity_id=tenant_id,
        raw_token=raw_token,
        exp=exp,
        email=body.email,
        metadata={
            "role": body.role,
            "organization_name": body.organization_name,
            "invited_by": tenant_id,
        },
        db=db,
    )

    logger.info("invite: created for email=%s role=%s by tenant=%s", body.email, body.role, tenant_id)

    return JSONResponse(
        status_code=201,
        content={
            "token": raw_token,
            "email": body.email,
            "role": body.role,
            "invite_url": f"/invite/{raw_token}",
            "expires_in_days": body.ttl_days,
            "token_id": record.get("id"),
        },
    )


# ---------------------------------------------------------------------------
# Public endpoints (no JWT — for invite page)
# ---------------------------------------------------------------------------

@router.get(
    "/invite/validate/{token}",
    tags=["public"],
    summary="Validate an invitation token (Phase 401)",
)
async def validate_invite(token: str) -> JSONResponse:
    """
    GET /invite/validate/{token}

    Public endpoint. Returns invite metadata if the token is valid.
    Response shape matches what the frontend expects:
        {role, organization_name, invited_by, expires_at}
    """
    # 1. Crypto verification
    claims = verify_access_token(token, expected_type=TokenType.INVITE)
    if not claims:
        return JSONResponse(status_code=401, content={
            "error": "INVITE_INVALID_OR_EXPIRED",
            "message": "This invitation is invalid or has expired.",
        })

    # 2. DB check: not used, not revoked
    db = _get_db()
    token_hash = _hash_token(token)

    try:
        res = (
            db.table("access_tokens")
            .select("id, used_at, revoked_at, metadata, expires_at")
            .eq("token_hash", token_hash)
            .eq("token_type", "invite")
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return JSONResponse(status_code=401, content={
                "error": "INVITE_NOT_FOUND",
                "message": "This invitation is no longer valid.",
            })

        row = rows[0]
        if row.get("revoked_at"):
            return JSONResponse(status_code=401, content={
                "error": "INVITE_REVOKED",
                "message": "This invitation has been revoked.",
            })
        if row.get("used_at"):
            return JSONResponse(status_code=401, content={
                "error": "INVITE_ALREADY_USED",
                "message": "This invitation has already been accepted.",
            })

        metadata = row.get("metadata") or {}

        return JSONResponse(status_code=200, content={
            "valid": True,
            "role": metadata.get("role", "staff"),
            "organization_name": metadata.get("organization_name", "Domaniqo"),
            "invited_by": metadata.get("invited_by"),
            "expires_at": row.get("expires_at"),
        })

    except Exception as exc:
        logger.exception("validate_invite DB error: %s", exc)
        # If DB fails, return basic info from claims
        return JSONResponse(status_code=200, content={
            "valid": True,
            "role": "staff",
            "organization_name": "Domaniqo",
        })


@router.post(
    "/invite/accept/{token}",
    tags=["public"],
    summary="Accept an invitation (Phase 401)",
)
async def accept_invite(token: str) -> JSONResponse:
    """
    POST /invite/accept/{token}

    Public endpoint. Consumes the invite token (one-use).
    In a full implementation, this would create a user record.
    For now: marks the token as used and returns success + role info.
    """
    db = _get_db()
    claims = validate_and_consume(
        raw_token=token,
        expected_type=TokenType.INVITE,
        db=db,
    )

    if not claims:
        return JSONResponse(status_code=401, content={
            "error": "INVITE_INVALID",
            "message": "This invitation is invalid, expired, or has already been accepted.",
        })

    metadata = claims.get("metadata") or {}

    # Log audit event
    try:
        db.table("audit_events").insert({
            "tenant_id": claims.get("entity_id", ""),
            "event_type": "invite_accepted",
            "entity_type": "invite",
            "entity_id": claims.get("db_id", ""),
            "payload": {
                "email": claims.get("email"),
                "role": metadata.get("role"),
            },
        }).execute()
    except Exception:
        pass  # Best-effort audit

    logger.info("invite: accepted email=%s role=%s", claims.get("email"), metadata.get("role"))

    return JSONResponse(status_code=200, content={
        "status": "accepted",
        "role": metadata.get("role", "staff"),
        "organization_name": metadata.get("organization_name", "Domaniqo"),
        "email": claims.get("email"),
    })
