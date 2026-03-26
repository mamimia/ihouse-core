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

# Phase 862 (Canonical Auth P7): single source of truth for roles
from services.canonical_roles import CANONICAL_ROLES as _VALID_ROLES


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
        # Phase 862 P28: Identity-only user — authenticated but no tenant membership.
        # Issue a limited JWT so they can access /welcome, /profile, /get-started.
        from services.canonical_roles import IDENTITY_ONLY
        logger.info(
            "auth/login: identity-only login for user=%s (%s). No tenant binding.",
            user_id, user_email,
        )
        user_metadata = signin.user.user_metadata or {}
        now = int(time.time())
        payload = {
            "sub": user_id,
            "tenant_id": "",           # No tenant — identity only
            "role": IDENTITY_ONLY,
            "email": user_email,
            "is_active": True,
            "force_reset": False,
            "iat": now,
            "exp": now + _TOKEN_TTL_SECONDS,
            "token_type": "session",
            "auth_method": "supabase",
        }
        token = jwt.encode(payload, jwt_secret, algorithm=_ALGORITHM)

        # Create server-side session
        user_agent = request.headers.get("User-Agent")
        ip_address = request.client.host if request.client else None
        try:
            supa_service = _get_service_db()
            create_session(
                supa_service,
                tenant_id="identity_only",
                token=token,
                expires_in_seconds=_TOKEN_TTL_SECONDS,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        except Exception as exc:
            logger.warning("auth/login: session creation failed for identity-only user=%s: %s", user_id, exc)

        return ok({
            "token": token,
            "tenant_id": "",
            "role": IDENTITY_ONLY,
            "email": user_email,
            "name": user_metadata.get("full_name", ""),
            "expires_in": _TOKEN_TTL_SECONDS,
            "supabase_access_token": supa_access_token,
            "supabase_refresh_token": supa_refresh_token,
        })
        
    tenant_id = tenant_info["tenant_id"]
    role = tenant_info.get("role", "worker")
    is_active = tenant_info.get("is_active", True)
    force_reset = user_metadata.get("force_reset", False)

    if role not in _VALID_ROLES:
        role = "worker"  # Phase 867: least-privilege fallback (unified with invite_router)

    # Step 3: Issue iHouse JWT with real identity
    now = int(time.time())
    payload = {
        "sub": user_id,           # Supabase Auth UUID — the REAL user identity
        "tenant_id": tenant_id,   # Resolved from tenant_permissions
        "role": role,             # Resolved from tenant_permissions
        "email": user_email,
        "is_active": is_active,
        "force_reset": force_reset,
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
        "language": tenant_info.get("language", "en"),
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
        # Phase 862 P28: Identity-only user — authenticated via Google but no tenant membership.
        from services.canonical_roles import IDENTITY_ONLY
        logger.info(
            "auth/google-callback: identity-only login for user=%s (%s). No tenant binding.",
            user_id, user_email,
        )
        now = int(time.time())
        payload = {
            "sub": user_id,
            "tenant_id": "",
            "role": IDENTITY_ONLY,
            "email": user_email,
            "is_active": True,
            "force_reset": False,
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
            create_session(
                supa_service,
                tenant_id="identity_only",
                token=token,
                expires_in_seconds=_TOKEN_TTL_SECONDS,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        except Exception as exc:
            logger.warning("auth/google-callback: session creation failed: %s", exc)

        return ok({
            "token": token,
            "tenant_id": "",
            "role": IDENTITY_ONLY,
            "email": user_email,
            "name": body.full_name,
            "expires_in": _TOKEN_TTL_SECONDS,
        })

    tenant_id = tenant_info["tenant_id"]
    role = tenant_info.get("role", "worker")
    is_active = tenant_info.get("is_active", True)
    if role not in _VALID_ROLES:
        role = "worker"  # Phase 867: least-privilege fallback (unified with invite_router)

    # Issue iHouse JWT
    # Fetch the user's metadata from Supabase Auth to retrieve force_reset
    # google_callback is a server-to-server call using the user_id, so we can use admin API
    try:
        user_obj = supa_service.auth.admin.get_user_by_id(user_id)
        user_metadata = user_obj.user.user_metadata or {}
        force_reset = user_metadata.get("force_reset", False)
        
        # Phase 945: Record explicit "Link Opened" step if in first-time onboarding
        if force_reset and "access_link_opened_at" not in user_metadata:
            user_metadata["access_link_opened_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            supa_service.auth.admin.update_user_by_id(user_id, {"user_metadata": user_metadata})
            
    except Exception as exc:
        logger.warning("auth/google-callback: failed to fetch user %s metadata: %s", user_id, exc)
        user_metadata = {}
        force_reset = False

    now = int(time.time())
    # Phase 948a: Include worker_roles so the frontend can resolve the
    # worker's specific sub-role (cleaner/checkin/checkout/maintenance).
    # The outer `role` stays 'worker' for access-control purposes.
    worker_roles = tenant_info.get("worker_roles") or []
    # Derive effective sub-role: use worker_role (singular) if set, else first element of worker_roles
    effective_worker_role = tenant_info.get("worker_role") or (worker_roles[0] if worker_roles else None)

    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "worker_roles": worker_roles,           # Phase 948a: sub-roles array
        "worker_role": effective_worker_role,   # Phase 948a: primary sub-role (nullable)
        "email": user_email,
        "is_active": is_active,
        "force_reset": force_reset,
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
        "language": tenant_info.get("language", "en"),
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
    summary="Save registration profile (no auto-provisioning — Phase 856A containment)",
    status_code=200,
    tags=["auth"],
)
async def register_profile(body: RegisterProfileRequest, request: Request) -> JSONResponse:
    """
    POST /auth/register/profile

    Phase 856A: AUTO-PROVISIONING DISABLED.

    Previously this endpoint auto-provisioned any signup as 'manager' on the
    default tenant — a critical privilege escalation hole.

    Now it:
    1. Finds the Supabase Auth user by email
    2. Saves profile data to user_metadata (for future lead processing)
    3. Returns 403 — user must be invited/approved through Pipeline A or B

    The user's metadata is preserved so that when an admin later invites or
    approves them, their profile info is already available.
    """
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

    # Phase 856A: NO auto-provisioning of tenant_permissions.
    # Only save profile metadata so it's available for future admin review.
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
                "registration_source": "google" if body.from_google else "email",
            },
        })
    except Exception as exc:
        logger.warning("auth/register/profile: metadata update failed: %s", exc)

    logger.info(
        "auth/register/profile: profile saved for user=%s email=%s name=%s "
        "(NO auto-provision — Phase 856A containment)",
        user_id, email, full_name,
    )

    # Return 403: profile saved but no access granted
    return err(
        "REGISTRATION_PENDING",
        "Thank you! Your profile has been saved. "
        "An administrator will review your request and grant access. "
        "You will be notified when your account is activated.",
        status=403,
    )


# ---------------------------------------------------------------------------
# POST /auth/change-password — User updates their own password over API
# ---------------------------------------------------------------------------

class ChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)

@router.post(
    "/auth/change-password",
    tags=["auth"],
    summary="Change own password (clears force_reset)",
    responses={
        200: {"description": "Password updated"},
        401: {"description": "Unauthorized"},
    },
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request
) -> JSONResponse:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return err("UNAUTHORIZED", "Missing token", status=401)
        
    token = auth_header.split(" ")[1]
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=[_ALGORITHM], options={"verify_aud": False})
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id", "")
        role = payload.get("role", "")
        email = payload.get("email", "")
    except Exception as e:
        return err("UNAUTHORIZED", f"Invalid token: {e}", status=401)

    if not user_id:
        return err("UNAUTHORIZED", "Missing sub", status=401)

    db = _get_service_db()
    if not db:
        return err("SUPABASE_NOT_CONFIGURED", "Supabase not configured", status=503)

    try:
        user_res = db.auth.admin.get_user_by_id(user_id)
        current_meta = user_res.user.user_metadata or {}
        current_meta["force_reset"] = False
        
        db.auth.admin.update_user_by_id(
            user_id,
            {"password": body.new_password, "user_metadata": current_meta}
        )
        
        # Issue a fresh JWT so the user doesn't have to log in again
        now = int(time.time())
        new_payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "email": email,
            "is_active": payload.get("is_active", True),
            "force_reset": False,
            "iat": now,
            "exp": now + _TOKEN_TTL_SECONDS,
            "token_type": "session",
            "auth_method": payload.get("auth_method", "password_reset"),
        }
        new_token = jwt.encode(new_payload, jwt_secret, algorithm=_ALGORITHM)
        
        return ok({
            "message": "Password updated successfully",
            "token": new_token,
            "expires_in": _TOKEN_TTL_SECONDS
        })
    except Exception as exc:
        logger.warning("auth/change-password: failed for user %s — %s", user_id, exc)
        return err("UPDATE_FAILED", str(exc), status=400)
