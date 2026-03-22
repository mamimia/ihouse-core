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

# Phase 862 (Canonical Auth P7): single source of truth for roles
from services.canonical_roles import CANONICAL_ROLES as _VALID_ROLES
# Phase 867: use INVITABLE_ROLES at accept time to block admin via invite
from services.canonical_roles import INVITABLE_ROLES as _INVITABLE_ROLES


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


class AcceptInviteRequest(BaseModel):
    password: str = Field(..., min_length=8, description="Password for the new user account")
    full_name: str = Field("", description="Full name of the user")


@router.post(
    "/invite/accept/{token}",
    tags=["public"],
    summary="Accept an invitation and create user account (Phase 401 + 767)",
)
async def accept_invite(token: str, body: AcceptInviteRequest) -> JSONResponse:
    """
    POST /invite/accept/{token}

    Public endpoint. Accepts the invite, creates a Supabase Auth user,
    provisions tenant_permissions with the invited role, and returns
    access credentials.

    Phase 767: completes the invite flow by actually creating the user.
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
    email = claims.get("email", "")
    raw_role = metadata.get("role", "worker")
    # Phase 867: validate against INVITABLE_ROLES (excludes admin) — not CANONICAL_ROLES
    # Phase 857 (audit B6): never trust metadata blindly
    if raw_role not in _INVITABLE_ROLES:
        logger.warning("invite/accept: role '%s' not in INVITABLE_ROLES — defaulting to 'worker'", raw_role)
        role = "worker"
    else:
        role = raw_role
    tenant_id = claims.get("entity_id", "")

    # Phase 767 + Fix 800b: Create Supabase Auth user + sign in for tokens
    # Uses TWO separate clients to avoid sign_in tainting service_role privileges.
    from supabase import create_client
    supa_url = os.environ.get("SUPABASE_URL", "")
    supa_service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    supa_anon_key = os.environ.get("SUPABASE_KEY", supa_service_key)
    user_id = None
    access_token = ""
    refresh_token = ""

    if supa_url and supa_service_key:
        supa_admin = create_client(supa_url, supa_service_key)
        try:
            # Client 1: service_role — create user
            result = supa_admin.auth.admin.create_user({
                "email": email,
                "password": body.password,
                "email_confirm": True,
                "user_metadata": {
                    "full_name": body.full_name.strip() if body.full_name else "",
                    "invited_role": role,
                },
            })
            user_id = str(result.user.id) if result.user else None
            logger.info("invite/accept: created new user %s (%s) role=%s", user_id, email, role)

        except Exception as exc:
            error_msg = str(exc).lower()
            if "already" in error_msg or "exists" in error_msg:
                # Phase 857 (audit B2): user already exists in Supabase Auth.
                # Use generate_link (proven pattern from Pipeline B) instead of
                # the old O(N) list_users() scan that broke at scale.
                logger.info(
                    "invite/accept: user %s already exists — using generate_link "
                    "to resolve user_id (Phase 857 fix)", email,
                )
                try:
                    frontend_url = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
                    link_res = supa_admin.auth.admin.generate_link(
                        {"type": "magiclink", "email": email,
                         "options": {"redirect_to": f"{frontend_url}/auth/callback"}}
                    )
                    user_id = str(link_res.user.id) if link_res and link_res.user else None
                except Exception as lookup_exc:
                    logger.warning("invite/accept: generate_link lookup failed: %s", lookup_exc)
            else:
                return JSONResponse(status_code=400, content={
                    "error": "USER_CREATION_FAILED",
                    "message": str(exc),
                })

        # Sign in (only possible for fresh users — skip silently for existing ones
        # since we don't know their current password, they can log in normally)
        if user_id:
            if not access_token:
                try:
                    supa_login = create_client(supa_url, supa_anon_key)
                    signin = supa_login.auth.sign_in_with_password({
                        "email": email,
                        "password": body.password,
                    })
                    if signin.session:
                        access_token = signin.session.access_token
                        refresh_token = signin.session.refresh_token
                except Exception as signin_exc:
                    # Best-effort — existing users with a different password won't sign in here
                    logger.info("invite/accept: sign-in skipped (likely existing user): %s", signin_exc)

            # Provision / re-provision tenant_permissions with the invited role
            from services.tenant_bridge import provision_user_tenant
            provision_user_tenant(
                supa_admin, user_id,
                tenant_id=tenant_id if tenant_id else None,
                role=role,
            )
            logger.info("invite/accept: provisioned user=%s email=%s role=%s", user_id, email, role)

    # Log audit event
    try:
        db.table("audit_events").insert({
            "tenant_id": tenant_id,
            "event_type": "invite_accepted",
            "entity_type": "invite",
            "entity_id": claims.get("db_id", ""),
            "payload": {
                "email": email,
                "role": role,
                "user_id": user_id,
            },
        }).execute()
    except Exception:
        pass  # Best-effort audit

    logger.info("invite: accepted email=%s role=%s user_id=%s", email, role, user_id)

    return JSONResponse(status_code=200, content={
        "status": "accepted",
        "role": role,
        "organization_name": metadata.get("organization_name", "Domaniqo"),
        "email": email,
        "user_id": user_id,
        "access_token": access_token,
        "refresh_token": refresh_token,
    })

