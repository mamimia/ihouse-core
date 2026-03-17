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

_VALID_ROLES = {"admin", "manager", "ops", "worker", "cleaner", "owner", "checkin", "checkout", "maintenance"}


# ---------------------------------------------------------------------------
# Cached Supabase clients — singleton per process (avoids per-request overhead)
# ---------------------------------------------------------------------------
_service_db = None
_anon_db = None


def _get_service_db():
    """Get cached Supabase client with service_role key."""
    global _service_db
    if _service_db is None:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
        _service_db = create_client(url, key)
    return _service_db


def _get_anon_db():
    """Get cached Supabase client with anon key (for sign_in)."""
    global _anon_db
    if _anon_db is None:
        from supabase import create_client
        url = os.environ["SUPABASE_URL"]
        key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        _anon_db = create_client(url, key)
    return _anon_db


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
        # Phase 831: No fallback to hardcoded tenant — if tenant_permissions
        # doesn't exist, the invite acceptance failed or never ran.
        # The user must be re-invited or manually provisioned.
        logger.warning(
            "auth/login: no tenant_permissions for user=%s (%s). "
            "invited_role=%s in metadata but no DB binding.",
            user_id, user_email, user_metadata.get("invited_role", "none"),
        )
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


# ---------------------------------------------------------------------------
# POST /auth/google-callback — Google OAuth login (identity already verified)
# ---------------------------------------------------------------------------

class GoogleCallbackRequest(BaseModel):
    user_id: str = Field(..., description="Supabase Auth UUID")
    email: str = Field(..., description="User email from Google")
    access_token: str = Field(default="", description="Supabase access token")
    full_name: str = Field(default="", description="Full name from Google profile")


@router.post(
    "/auth/google-callback",
    summary="Complete Google OAuth login — resolves tenant/role and issues iHouse JWT",
    status_code=200,
    tags=["auth"],
)
async def google_callback(body: GoogleCallbackRequest, request: Request) -> JSONResponse:
    """
    POST /auth/google-callback

    Called by the frontend after Supabase Google OAuth completes.
    The user is already authenticated by Google → Supabase.
    This endpoint resolves tenant/role and issues an iHouse JWT.
    """
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET not set", status=503)

    user_id = body.user_id
    user_email = body.email

    # Look up tenant_permissions
    from services.tenant_bridge import lookup_user_tenant
    try:
        supa_service = _get_service_db()
        tenant_info = lookup_user_tenant(supa_service, user_id)
    except Exception as exc:
        logger.warning("auth/google-callback: tenant lookup failed for user=%s: %s", user_id, exc)
        tenant_info = None

    if not tenant_info:
        # New Google user — no tenant binding yet
        return err(
            "NO_TENANT_BINDING",
            "Account exists but is not assigned to any organization. Complete registration.",
            status=403,
        )

    tenant_id = tenant_info["tenant_id"]
    role = tenant_info.get("role", "manager")
    if role not in _VALID_ROLES:
        role = "manager"

    # Issue iHouse JWT
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "email": user_email,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
        "token_type": "session",
        "auth_method": "google",
    }
    token = jwt.encode(payload, jwt_secret, algorithm=_ALGORITHM)

    # Create server-side session
    user_agent = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    try:
        supa_service = _get_service_db()
        session = create_session(
            supa_service,
            tenant_id=tenant_id,
            token=token,
            expires_in_seconds=_TOKEN_TTL_SECONDS,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except Exception as exc:
        logger.warning("auth/google-callback: session creation failed: %s", exc)
        session = {}

    logger.info(
        "auth/google-callback: user=%s email=%s tenant=%s role=%s",
        user_id, user_email, tenant_id, role,
    )

    return ok({
        "token": token,
        "token_type": "session",
        "auth_method": "google",
        "user_id": user_id,
        "email": user_email,
        "tenant_id": tenant_id,
        "role": role,
        "full_name": body.full_name,
        "expires_in": _TOKEN_TTL_SECONDS,
        "session": session,
    })


# ---------------------------------------------------------------------------
# POST /auth/register/profile — Complete registration profile
# ---------------------------------------------------------------------------

class RegisterProfileRequest(BaseModel):
    email: str = Field(..., description="User email")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    country: str = Field(default="", description="Country")
    phone: str = Field(default="", description="Phone number")
    listings_count: str = Field(default="", description="Portfolio size")
    avg_nightly_rate: str = Field(default="", description="Average nightly rate")
    from_google: bool = Field(default=False, description="Whether user came via Google OAuth")


@router.post(
    "/auth/register/profile",
    summary="Complete registration — save profile and provision tenant",
    status_code=200,
    tags=["auth"],
)
async def register_profile(body: RegisterProfileRequest, request: Request) -> JSONResponse:
    """
    POST /auth/register/profile

    Called after Supabase signUp or Google OAuth for new users.
    1. Finds the Supabase Auth user by email
    2. Provisions tenant_permissions row
    3. Issues iHouse JWT so user can log in immediately
    """
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET not set", status=503)

    email = body.email.strip()
    full_name = f"{body.first_name.strip()} {body.last_name.strip()}".strip()

    # Find user in Supabase Auth by email
    try:
        supa_service = _get_service_db()
        users_resp = supa_service.auth.admin.list_users()
        user = None
        for u in (users_resp or []):
            if hasattr(u, 'email') and u.email == email:
                user = u
                break
    except Exception as exc:
        logger.warning("auth/register/profile: user lookup failed for email=%s: %s", email, exc)
        return err("USER_NOT_FOUND", "Could not find your account. Please register first.", status=404)

    if not user:
        return err("USER_NOT_FOUND", "Could not find your account. Please register first.", status=404)

    user_id = str(user.id)

    # Provision tenant_permissions
    from services.tenant_bridge import provision_user_tenant
    try:
        if not supa_service:
            supa_service = _get_service_db()
        provision_user_tenant(supa_service, user_id)
    except Exception as exc:
        logger.warning("auth/register/profile: tenant provision failed: %s", exc)

    # Update user metadata with profile info
    try:
        supa_service.auth.admin.update_user_by_id(user_id, {
            "user_metadata": {
                "full_name": full_name,
                "first_name": body.first_name.strip(),
                "last_name": body.last_name.strip(),
                "country": body.country.strip(),
                "phone": body.phone.strip(),
                "listings_count": body.listings_count,
                "avg_nightly_rate": body.avg_nightly_rate,
            },
        })
    except Exception as exc:
        logger.warning("auth/register/profile: metadata update failed: %s", exc)

    # Issue JWT
    from services.tenant_bridge import DEFAULT_TENANT_ID, DEFAULT_SIGNUP_ROLE
    now = int(time.time())
    payload = {
        "sub": user_id,
        "tenant_id": DEFAULT_TENANT_ID,
        "role": DEFAULT_SIGNUP_ROLE,
        "email": email,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
        "token_type": "session",
        "auth_method": "google" if body.from_google else "supabase",
    }
    token = jwt.encode(payload, jwt_secret, algorithm=_ALGORITHM)

    # Create session
    user_agent = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None
    try:
        session = create_session(
            supa_service,
            tenant_id=DEFAULT_TENANT_ID,
            token=token,
            expires_in_seconds=_TOKEN_TTL_SECONDS,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except Exception as exc:
        logger.warning("auth/register/profile: session creation failed: %s", exc)
        session = {}

    logger.info(
        "auth/register/profile: user=%s email=%s name=%s (registration complete)",
        user_id, email, full_name,
    )

    return ok({
        "token": token,
        "token_type": "session",
        "user_id": user_id,
        "email": email,
        "tenant_id": DEFAULT_TENANT_ID,
        "role": DEFAULT_SIGNUP_ROLE,
        "full_name": full_name,
        "expires_in": _TOKEN_TTL_SECONDS,
        "session": session,
    })
