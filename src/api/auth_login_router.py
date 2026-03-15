"""
Auth Login Router — Production Login via Supabase Auth
========================================================

Production-grade login endpoint: email + password → Supabase Auth → identity resolution.

Endpoints:
    POST /auth/login    — Login with email + password (production)

Design:
    1. Accepts {email, password} — no role, no tenant_id from client
    2. Calls Supabase Auth sign_in_with_password
    3. Gets user UUID from Supabase Auth
    4. Looks up tenant_permissions to resolve tenant_id + role
    5. Issues iHouse JWT with: sub = user_id (UUID), tenant_id, role
    6. Creates server-side session for tracking/revocation

This replaces the dev-mode login (/auth/dev-login) for production use.
"""
from __future__ import annotations

import logging
import os
import time

import jwt
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.envelope import ok, err
from services.session import create_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 86_400  # 24 hours

_VALID_ROLES = {"admin", "manager", "ops", "worker", "owner", "checkin", "checkout", "maintenance"}


def _get_service_db():
    """Get Supabase client with service_role key."""
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def _get_anon_db():
    """Get Supabase client with anon key (for sign_in)."""
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1, description="User email address")
    password: str = Field(..., min_length=1, description="User password")


# ---------------------------------------------------------------------------
# POST /auth/login — Production login
# ---------------------------------------------------------------------------

@router.post(
    "/auth/login",
    summary="Login with email + password (production)",
    status_code=200,
    tags=["auth"],
)
async def login(body: LoginRequest, request: Request) -> JSONResponse:
    """
    POST /auth/login

    Production login flow:
    1. Authenticate via Supabase Auth (email + password)
    2. Look up tenant_permissions for the user's UUID
    3. Issue iHouse JWT with real identity: sub=user_id, tenant_id, role
    4. Create server-side session

    No role selector. No tenant_id input. Identity is server-resolved.
    """
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET not set", status=503)

    supa_url = os.environ.get("SUPABASE_URL", "")
    if not supa_url:
        return err("AUTH_NOT_CONFIGURED", "SUPABASE_URL not set", status=503)

    # Step 1: Authenticate with Supabase Auth
    try:
        supa_login = _get_anon_db()
        signin = supa_login.auth.sign_in_with_password({
            "email": body.email.strip(),
            "password": body.password,
        })
    except Exception as exc:
        error_msg = str(exc).lower()
        if "invalid" in error_msg or "credentials" in error_msg or "not found" in error_msg:
            return err("INVALID_CREDENTIALS", "Invalid email or password", status=401)
        logger.exception("auth/login: Supabase Auth error: %s", exc)
        return err("AUTH_ERROR", f"Authentication failed: {exc}", status=500)

    if not signin.user:
        return err("INVALID_CREDENTIALS", "Invalid email or password", status=401)

    user_id = str(signin.user.id)
    user_email = signin.user.email or body.email.strip()
    user_metadata = signin.user.user_metadata or {}

    # Keep the Supabase access/refresh tokens for the frontend
    supa_access_token = signin.session.access_token if signin.session else ""
    supa_refresh_token = signin.session.refresh_token if signin.session else ""

    # Step 2: Look up tenant_permissions for this user UUID
    from services.tenant_bridge import lookup_user_tenant
    try:
        supa_service = _get_service_db()
        tenant_info = lookup_user_tenant(supa_service, user_id)
    except Exception as exc:
        logger.warning("auth/login: tenant lookup failed for user=%s: %s", user_id, exc)
        tenant_info = None

    if not tenant_info:
        # Fallback: check user_metadata for invited_role (from invite flow)
        invited_role = user_metadata.get("invited_role", "")
        if invited_role:
            tenant_id = "tenant_e2e_amended"  # V1: single tenant
            role = invited_role
            logger.info("auth/login: using invited_role=%s from metadata for user=%s", role, user_id)
        else:
            return err(
                "NO_TENANT_BINDING",
                "Your account exists but is not assigned to any organization. Contact your administrator.",
                status=403,
            )
    else:
        tenant_id = tenant_info["tenant_id"]
        role = tenant_info.get("role", "manager")

    if role not in _VALID_ROLES:
        role = "manager"  # safe fallback

    # Step 3: Issue iHouse JWT with real identity
    now = int(time.time())
    payload = {
        "sub": user_id,           # Supabase Auth UUID — the REAL user identity
        "tenant_id": tenant_id,   # Resolved from tenant_permissions
        "role": role,             # Resolved from tenant_permissions
        "email": user_email,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
        "token_type": "session",
        "auth_method": "supabase",  # Distinguishes from dev tokens
    }
    token = jwt.encode(payload, jwt_secret, algorithm=_ALGORITHM)

    # Step 4: Create server-side session
    user_agent = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None

    try:
        session = create_session(
            supa_service,
            tenant_id=tenant_id,
            token=token,
            expires_in_seconds=_TOKEN_TTL_SECONDS,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except Exception as exc:
        logger.exception("auth/login: session creation failed: %s", exc)
        session = {}

    logger.info(
        "auth/login: user=%s email=%s tenant=%s role=%s (production login)",
        user_id, user_email, tenant_id, role,
    )

    return ok({
        "token": token,
        "token_type": "session",
        "auth_method": "supabase",
        "user_id": user_id,
        "email": user_email,
        "tenant_id": tenant_id,
        "role": role,
        "full_name": user_metadata.get("full_name", ""),
        "expires_in": _TOKEN_TTL_SECONDS,
        "session": session,
        # Include Supabase tokens so frontend can use Supabase Realtime
        "supabase_access_token": supa_access_token,
        "supabase_refresh_token": supa_refresh_token,
    })
