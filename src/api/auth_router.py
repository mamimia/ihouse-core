"""
Phase 179 — Auth Token Issuer
Phase 397 — JWT Role Claim
Phase 186 — Auth Logout

POST /auth/token  — Issues a signed HS256 JWT for a given tenant_id.
POST /auth/logout — Client-side logout: clears ihouse_token cookie + returns 200.

Contracts:
    POST /auth/token
        Request body: {"tenant_id": str, "secret": str}
        Response 200: {"token": str, "tenant_id": str, "expires_in": int}
        Response 401: wrong secret
        Response 422: missing/invalid body

    POST /auth/logout
        Body: (none required)
        Response 200: {"message": "Logged out"}
        Sets Set-Cookie: ihouse_token=; Max-Age=0  (tells browser to delete cookie)
        Not JWT-protected — must work even with expired / missing tokens.

Invariants:
    - Uses IHOUSE_JWT_SECRET as the signing key.
    - If IHOUSE_JWT_SECRET is not set for /token, returns 503.
    - The "secret" in the request body is compared against IHOUSE_DEV_PASSWORD
      (defaults to "dev" when not set — safe for local use only).
    - Token sub = tenant_id, exp = now + 24h.
    - Production systems should replace this with Supabase Auth.
    - /auth/logout is NOT protected by jwt_auth — clients call it even when
      the token is expired or missing.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.envelope import ok, err

logger = logging.getLogger(__name__)

router = APIRouter()

from api.auth import jwt_auth  # noqa: E402  Phase 467

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 86_400  # 24 hours


# Phase 862 (Canonical Auth P7): single source of truth for roles
from services.canonical_roles import CANONICAL_ROLES as VALID_ROLES


class TokenRequest(BaseModel):
    tenant_id: str
    secret: str
    role: str = "manager"  # Phase 397: optional role, must be a valid role


@router.post(
    "/auth/token",
    tags=["auth"],
    summary="Issue a dev JWT for a tenant (dev-only)",
    responses={
        200: {"description": "JWT issued"},
        401: {"description": "Wrong secret"},
        503: {"description": "Auth not configured — IHOUSE_JWT_SECRET not set"},
    },
)
async def issue_token(body: TokenRequest) -> JSONResponse:
    """
    Issue a signed HS256 JWT for the given tenant_id.

    **Request body:**
    ```json
    {"tenant_id": "my-tenant", "secret": "dev"}
    ```

    **Response:**
    ```json
    {"token": "eyJ...", "tenant_id": "my-tenant", "expires_in": 86400}
    ```

    The token is signed with IHOUSE_JWT_SECRET (HS256).
    The request secret is validated against IHOUSE_DEV_PASSWORD (default: "dev").

    This is a development-only endpoint. Replace with Supabase Auth in production.
    """
    # Phase 862 (Canonical Auth P8): production gate
    # This endpoint issues arbitrary dev JWTs — must NEVER be available in production.
    if os.environ.get("IHOUSE_DEV_MODE", "").lower() != "true":
        return err("DEV_ONLY_ENDPOINT", "POST /auth/token is disabled in production.", status=403)

    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET is not set. Auth endpoint unavailable.", status=503)

    dev_password = os.environ.get("IHOUSE_DEV_PASSWORD", "dev")

    if not body.tenant_id or not body.tenant_id.strip():
        return err("VALIDATION_ERROR", "tenant_id is required", status=422)

    if body.secret != dev_password:
        logger.warning("auth/token: wrong secret for tenant_id=%s", body.tenant_id)
        return err("UNAUTHORIZED", "Invalid secret", status=401)

    tenant_id = body.tenant_id.strip()

    # Phase 759: Role authority — read canonical role from DB, not from request.
    # The request body role is kept for backward compat but DB value always wins.
    from services.role_authority import resolve_role as _resolve_role
    try:
        db = _get_supabase_admin()
        role = _resolve_role(db, tenant_id, tenant_id, requested_role=body.role) if db else (body.role or "manager")
    except Exception:
        role = body.role.strip().lower() if body.role else "manager"

    if role not in VALID_ROLES:
        return err("INVALID_ROLE", f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}", status=422)

    now = int(time.time())
    payload = {
        "sub": tenant_id,         # Phase 862 P22: in dev mode, sub=tenant_id (no real UUID)
        "tenant_id": tenant_id,   # Phase 862 P22: explicit claim for format unification
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
        "role": role,  # Phase 759: DB-authoritative role
        "token_type": "session",
        "auth_method": "dev_token",  # Phase 862 P22: identifies token origin
    }

    token = jwt.encode(payload, jwt_secret, algorithm=_ALGORITHM)

    logger.info("auth/token: issued token for tenant_id=%s role=%s (db-resolved)", tenant_id, role)
    return ok({
        "token": token,
        "tenant_id": tenant_id,
        "role": role,
        "expires_in": _TOKEN_TTL_SECONDS,
    })


# ---------------------------------------------------------------------------
# Phase 186 — POST /auth/logout
# ---------------------------------------------------------------------------

@router.post(
    "/auth/logout",
    tags=["auth"],
    summary="Log out and clear session token",
    responses={
        200: {"description": "Logged out successfully"},
    },
)
async def logout() -> JSONResponse:
    """
    Phase 186: Client-side logout.

    Returns 200 and instructs the browser to delete the `ihouse_token` cookie
    via `Set-Cookie: ihouse_token=; Max-Age=0`.

    The caller (UI/client) is expected to:
      - Delete localStorage['ihouse_token']
      - Redirect to /login

    This endpoint is intentionally NOT protected by jwt_auth so that it can
    be called even when the token is expired or missing.
    """
    response = ok({"message": "Logged out"})
    # Tell the browser to delete the cookie (Max-Age=0 = expire immediately)
    response.set_cookie(
        key="ihouse_token",
        value="",
        max_age=0,
        path="/",
        samesite="lax",
        httponly=False,   # must be readable by JS (same as login sets it)
    )
    logger.info("auth/logout: token cookie cleared")
    return response


# ---------------------------------------------------------------------------
# Phase 276 — POST /auth/supabase-verify
# ---------------------------------------------------------------------------

class SupabaseVerifyRequest(BaseModel):
    token: str


@router.post(
    "/auth/supabase-verify",
    tags=["auth"],
    summary="Verify a Supabase-issued JWT and return decoded claims",
    responses={
        200: {"description": "JWT valid — returns decoded claims"},
        403: {"description": "Invalid, expired, or malformed token"},
        503: {"description": "IHOUSE_JWT_SECRET not configured"},
    },
)
async def supabase_verify(body: SupabaseVerifyRequest) -> JSONResponse:
    """
    Phase 276: Verify a Supabase Auth JWT and return its decoded claims.

    Accepts the JWT issued by Supabase Auth (aud="authenticated") and validates
    it against IHOUSE_JWT_SECRET. Returns decoded claims on success.

    **Request body:**
    ```json
    {"token": "eyJ..."}
    ```

    **Response (200):**
    ```json
    {
        "valid": true,
        "sub": "user-uuid",
        "aud": "authenticated",
        "role": "authenticated",
        "email": "user@example.com",
        "exp": 1234567890,
        "token_type": "supabase"
    }
    ```

    Used for integration testing and debugging. The `token_type` field
    is `"supabase"` for Supabase Auth tokens and `"internal"` for
    tokens issued by POST /auth/token.
    """
    from api.auth import decode_jwt_claims  # avoid circular at module level

    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET is not set.", status=503)

    if not body.token or not body.token.strip():
        return err("TOKEN_REQUIRED", "token field is required", status=403)

    claims = decode_jwt_claims(body.token.strip(), jwt_secret)
    if not claims:
        return err("INVALID_TOKEN", "Token is invalid or expired", status=403)

    sub = claims.get("sub", "")
    aud = claims.get("aud", "")
    role = claims.get("role", "")
    token_type = "supabase" if (aud == "authenticated" or role == "authenticated") else "internal"

    logger.info(
        "auth/supabase-verify: validated token sub=%s type=%s",
        sub, token_type,
    )
    return ok({
        "valid": True,
        "sub": sub,
        "aud": aud,
        "role": role,
        "email": claims.get("email", ""),
        "exp": claims.get("exp"),
        "token_type": token_type,
    })


# ---------------------------------------------------------------------------
# Phase 467 — Supabase Auth: Real User Signup / Signin / Me
# ---------------------------------------------------------------------------

def _get_supabase_admin():
    """
    Return a Supabase client with service_role key for admin Auth operations.
    """
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


class SignUpRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


class SignInRequest(BaseModel):
    email: str
    password: str


@router.post(
    "/auth/signup",
    tags=["auth"],
    summary="Register a new user via Supabase Auth (Phase 467)",
    responses={
        200: {"description": "User created — returns access token"},
        400: {"description": "Signup failed (user exists, weak password, etc.)"},
        503: {"description": "Supabase not configured"},
    },
)
async def supabase_signup(body: SignUpRequest) -> JSONResponse:
    """
    Phase 467: Create a real user in Supabase Auth.

    **Request body:**
    ```json
    {"email": "admin@domaniqo.com", "password": "...", "full_name": "Nir Admin"}
    ```

    **Response (200):**
    ```json
    {
        "user_id": "uuid",
        "email": "admin@domaniqo.com",
        "access_token": "eyJ...",
        "refresh_token": "...",
        "expires_in": 3600
    }
    ```

    The returned access_token is a Supabase-signed JWT and can be used
    directly with all iHouse API endpoints that require JWT auth.
    """
    db = _get_supabase_admin()
    if not db:
        return err("SUPABASE_NOT_CONFIGURED", "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.", status=503)

    try:
        result = db.auth.admin.create_user({
            "email": body.email.strip(),
            "password": body.password,
            "email_confirm": True,  # Auto-confirm for admin-created users
            "user_metadata": {"full_name": body.full_name.strip()} if body.full_name else {},
        })

        user = result.user
        if not user:
            return err("SIGNUP_FAILED", "User creation returned no user object.", status=400)

        # Phase 862 (Canonical Auth P1): signup creates IDENTITY ONLY.
        # No tenant_permissions row is auto-provisioned.
        # The user must be invited/approved through Pipeline A (invite) or
        # Pipeline B (staff onboarding) to get tenant membership + role.
        # This closes the privilege escalation hole where anyone who called
        # /auth/signup was auto-provisioned as manager on DEFAULT_TENANT_ID.

        # Sign in immediately to get Supabase tokens (identity-level only)
        signin_result = db.auth.sign_in_with_password({
            "email": body.email.strip(),
            "password": body.password,
        })

        session = signin_result.session
        logger.info("auth/signup: created identity %s (%s) — no tenant provisioned", user.id, body.email)
        return ok({
            "user_id": str(user.id),
            "email": body.email.strip(),
            "access_token": session.access_token if session else "",
            "refresh_token": session.refresh_token if session else "",
            "expires_in": session.expires_in if session else 0,
        })
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("auth/signup: failed for %s — %s", body.email, error_msg)
        return err("SIGNUP_FAILED", error_msg, status=400)


@router.post(
    "/auth/signin",
    tags=["auth"],
    summary="Sign in with email + password via Supabase Auth (Phase 467)",
    responses={
        200: {"description": "Authenticated — returns access token"},
        401: {"description": "Invalid credentials"},
        503: {"description": "Supabase not configured"},
    },
)
async def supabase_signin(body: SignInRequest) -> JSONResponse:
    """
    Phase 467: Sign in an existing Supabase Auth user.

    **Request body:**
    ```json
    {"email": "admin@domaniqo.com", "password": "..."}
    ```

    **Response (200):**
    ```json
    {
        "user_id": "uuid",
        "email": "admin@domaniqo.com",
        "access_token": "eyJ...",
        "refresh_token": "...",
        "expires_in": 3600
    }
    ```
    """
    db = _get_supabase_admin()
    if not db:
        return err("SUPABASE_NOT_CONFIGURED", "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.", status=503)

    try:
        result = db.auth.sign_in_with_password({
            "email": body.email.strip(),
            "password": body.password,
        })

        session = result.session
        user = result.user
        if not session or not user:
            return err("AUTH_FAILED", "Invalid credentials.", status=401)

        # Phase 760: Look up the user's tenant mapping.
        from services.tenant_bridge import lookup_user_tenant
        tenant_record = lookup_user_tenant(db, str(user.id))
        tenant_id = tenant_record.get("tenant_id", "") if tenant_record else ""
        role = tenant_record.get("role", "") if tenant_record else ""

        logger.info(
            "auth/signin: authenticated %s (%s) → tenant=%s role=%s",
            user.id, body.email, tenant_id, role,
        )
        return ok({
            "user_id": str(user.id),
            "email": body.email.strip(),
            "tenant_id": tenant_id,
            "role": role,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_in": session.expires_in,
        })
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("auth/signin: failed for %s — %s", body.email, error_msg)
        return err("AUTH_FAILED", error_msg, status=401)


# ---------------------------------------------------------------------------
# Phase 768 — Password Reset / Recovery
# ---------------------------------------------------------------------------

class PasswordResetRequest(BaseModel):
    email: str


class PasswordUpdateRequest(BaseModel):
    user_id: str
    new_password: str


@router.post(
    "/auth/password-reset",
    tags=["auth"],
    summary="Request a password reset email (Phase 768)",
    responses={
        200: {"description": "Reset email sent (always returns 200 for security)"},
        503: {"description": "Supabase not configured"},
    },
)
async def password_reset_request(body: PasswordResetRequest) -> JSONResponse:
    """
    Phase 768: Initiate password reset via Supabase Auth.

    Sends a recovery email to the user. Always returns 200 regardless
    of whether the email exists (prevents user enumeration).

    The redirect URL comes from IHOUSE_PASSWORD_RESET_REDIRECT env var
    or defaults to the CORS origin.
    """
    db = _get_supabase_admin()
    if not db:
        return err("SUPABASE_NOT_CONFIGURED", "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.", status=503)

    email = body.email.strip().lower()
    redirect_to = os.environ.get(
        "IHOUSE_PASSWORD_RESET_REDIRECT",
        os.environ.get("IHOUSE_CORS_ORIGINS", "http://localhost:3000").split(",")[0].strip()
    )

    try:
        db.auth.reset_password_email(email, options={"redirect_to": redirect_to})
        logger.info("auth/password-reset: sent recovery email to %s", email)
    except Exception as exc:
        # Log but don't expose whether the email exists
        logger.warning("auth/password-reset: failed for %s — %s", email, exc)

    # Always 200 — don't reveal whether email exists
    return ok({"message": "If that email is registered, a reset link has been sent."})


@router.post(
    "/auth/password-update",
    tags=["auth"],
    summary="Update a user's password (Phase 768, admin only)",
    responses={
        200: {"description": "Password updated"},
        400: {"description": "Update failed"},
        403: {"description": "Not authorized — admin role required"},
        503: {"description": "Supabase not configured"},
    },
)
async def password_update(
    body: PasswordUpdateRequest,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 768: Update a user's password via admin API.
    Phase 862 P2: JWT-protected.
    Phase 862 P11: Admin role enforced — non-admin callers get 403.

    This is for admin-initiated password resets (e.g. from support).
    Users who click the recovery link go through Supabase's built-in flow.
    """
    # ── Phase 862 P11: Extract role from JWT and enforce admin ──
    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    caller_role = None
    if raw_token:
        from api.auth import decode_jwt_claims
        jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
        if jwt_secret:
            claims = decode_jwt_claims(raw_token, jwt_secret)
            caller_role = claims.get("role", "")

    if caller_role != "admin":
        logger.warning(
            "auth/password-update: rejected — caller role='%s' (admin required), tenant=%s",
            caller_role, tenant_id,
        )
        return err("ADMIN_REQUIRED", "Only admin users can update other users' passwords.", status=403)

    db = _get_supabase_admin()
    if not db:
        return err("SUPABASE_NOT_CONFIGURED", "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.", status=503)

    try:
        db.auth.admin.update_user_by_id(
            body.user_id,
            {"password": body.new_password},
        )
        logger.info("auth/password-update: updated for user %s (by admin tenant=%s)", body.user_id, tenant_id)
        return ok({"message": "Password updated successfully.", "user_id": body.user_id})
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("auth/password-update: failed for user %s — %s", body.user_id, error_msg)
        return err("UPDATE_FAILED", error_msg, status=400)


# ---------------------------------------------------------------------------
# Phase 862 P15: Identity surface — GET /auth/identity
# ---------------------------------------------------------------------------

@router.get(
    "/auth/identity",
    tags=["auth"],
    summary="Get identity surface for the authenticated user (Phase 862 P15)",
    responses={
        200: {"description": "Identity surface returned"},
        403: {"description": "Invalid or missing JWT"},
        503: {"description": "JWT secret not configured"},
    },
)
async def get_identity_surface(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P15: Canonical identity surface.

    Returns the authenticated user's identity, membership status, and intake status.
    This is the single endpoint that all frontends use to decide what surface to show.

    Response:
        {
            "user_id": "supabase-uuid",
            "email": "...",           # from JWT claims or user_metadata
            "full_name": "...",       # from JWT claims or user_metadata
            "has_membership": true|false,
            "tenant_id": "...",       # if has_membership
            "role": "...",            # if has_membership
            "is_active": true|false,  # if has_membership
            "intake_status": "...",   # pending_review | approved | rejected | null
        }
    """
    # Extract full claims from the JWT
    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""

    claims = {}
    user_id = tenant_id  # jwt_auth returns sub, which may be user_id or tenant_id
    if raw_token:
        from api.auth import decode_jwt_claims
        jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
        if jwt_secret:
            claims = decode_jwt_claims(raw_token, jwt_secret)
            # In new format, sub=user_id. In legacy format, sub=tenant_id.
            user_id = claims.get("sub", tenant_id)

    # Build response
    result = {
        "user_id": user_id,
        "email": claims.get("email", ""),
        "full_name": claims.get("full_name", ""),
        "has_membership": False,
        "tenant_id": None,
        "role": None,
        "is_active": None,
        "intake_status": None,
    }

    # Lookup tenant_permissions (membership)
    try:
        from services.tenant_bridge import lookup_user_tenant
        from api.db import get_db
        db = get_db()
        if db:
            membership = lookup_user_tenant(db, user_id)
            if membership:
                result["has_membership"] = True
                result["tenant_id"] = membership.get("tenant_id")
                result["role"] = membership.get("role")
                result["is_active"] = membership.get("is_active", True)
    except Exception as exc:
        logger.warning("auth/identity: tenant lookup failed for user=%s: %s", user_id, exc)

    # Lookup intake_requests (submitter status)
    try:
        from api.db import get_db
        db = get_db()
        if db:
            intake_result = (
                db.table("intake_requests")
                .select("status")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = intake_result.data or []
            if rows:
                result["intake_status"] = rows[0].get("status")
    except Exception as exc:
        logger.warning("auth/identity: intake lookup failed for user=%s: %s", user_id, exc)

    return ok(result)


# ---------------------------------------------------------------------------
# Phase 862 P18: Profile — GET/PATCH /auth/profile
# ---------------------------------------------------------------------------

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    language: Optional[str] = None


@router.get(
    "/auth/profile",
    tags=["auth"],
    summary="Get profile for the authenticated user (Phase 862 P18)",
    responses={
        200: {"description": "Profile returned"},
        403: {"description": "Not authenticated"},
    },
)
async def get_profile(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P29: Returns the authenticated user's canonical profile.
    Includes Supabase Auth metadata, linked providers, and membership context.
    Accessible to ALL authenticated users regardless of role.
    """
    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""

    claims = {}
    user_id = tenant_id
    if raw_token:
        from api.auth import decode_jwt_claims
        jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
        if jwt_secret:
            claims = decode_jwt_claims(raw_token, jwt_secret)
            user_id = claims.get("sub", tenant_id)

    # Start with JWT claims as baseline
    profile = {
        "user_id": user_id,
        "email": claims.get("email", ""),
        "full_name": "",
        "phone": "",
        "avatar_url": "",
        "language": "",
        "providers": [],        # Phase 862 P29: linked login methods
        "role": claims.get("role", ""),
        "tenant_id": claims.get("tenant_id", ""),
        "has_membership": bool(claims.get("tenant_id", "")),
    }

    # Enrich from Supabase Auth (real source of truth for user metadata)
    try:
        supa_admin = _get_supabase_admin()
        if supa_admin:
            user_obj = supa_admin.auth.admin.get_user_by_id(user_id)
            if user_obj and user_obj.user:
                user = user_obj.user
                metadata = user.user_metadata or {}
                profile["email"] = user.email or profile["email"]
                profile["full_name"] = metadata.get("full_name", "") or metadata.get("name", "")
                profile["phone"] = metadata.get("phone", "") or user.phone or ""
                profile["avatar_url"] = metadata.get("avatar_url", "")
                # Extract linked providers
                identities = getattr(user, "identities", None) or []
                providers = []
                for identity in identities:
                    provider = getattr(identity, "provider", None) or (identity.get("provider") if isinstance(identity, dict) else None)
                    if provider and provider not in providers:
                        providers.append(provider)
                profile["providers"] = providers
    except Exception as exc:
        logger.warning("auth/profile: Supabase metadata fetch failed for user=%s: %s", user_id, exc)

    # Enrich from tenant_permissions if available
    try:
        from services.tenant_bridge import lookup_user_tenant
        from api.db import get_db
        db = get_db()
        if db:
            membership = lookup_user_tenant(db, user_id)
            if membership:
                profile["language"] = membership.get("language", "") or ""
                profile["has_membership"] = True
                profile["role"] = membership.get("role", profile["role"])
                profile["tenant_id"] = membership.get("tenant_id", profile["tenant_id"])
    except Exception as exc:
        logger.warning("auth/profile: tenant lookup failed for user=%s: %s", user_id, exc)

    return ok(profile)


@router.patch(
    "/auth/profile",
    tags=["auth"],
    summary="Update profile for the authenticated user (Phase 862 P18)",
    responses={
        200: {"description": "Profile updated"},
        403: {"description": "Not authenticated"},
    },
)
async def update_profile(
    body: ProfileUpdateRequest,
    request: Request,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """
    Phase 862 P18: Update the authenticated user's profile.
    Only the caller can update their own profile.
    """
    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""

    user_id = tenant_id
    if raw_token:
        from api.auth import decode_jwt_claims
        jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
        if jwt_secret:
            claims = decode_jwt_claims(raw_token, jwt_secret)
            user_id = claims.get("sub", tenant_id)

    updated_fields = {}

    # Update language in tenant_permissions if applicable
    if body.language is not None:
        try:
            from api.db import get_db
            db = get_db()
            if db:
                db.table("tenant_permissions").update({
                    "language": body.language.strip(),
                }).eq("user_id", user_id).execute()
                updated_fields["language"] = body.language.strip()
        except Exception as exc:
            logger.warning("auth/profile: language update failed for user=%s: %s", user_id, exc)

    # Update Supabase Auth user_metadata (full_name, phone) if applicable
    if body.full_name is not None or body.phone is not None:
        try:
            supa_admin = _get_supabase_admin()
            if supa_admin:
                metadata_update = {}
                if body.full_name is not None:
                    metadata_update["full_name"] = body.full_name.strip()
                    updated_fields["full_name"] = body.full_name.strip()
                if body.phone is not None:
                    metadata_update["phone"] = body.phone.strip()
                    updated_fields["phone"] = body.phone.strip()
                if metadata_update:
                    supa_admin.auth.admin.update_user_by_id(
                        user_id,
                        {"user_metadata": metadata_update},
                    )
        except Exception as exc:
            logger.warning("auth/profile: metadata update failed for user=%s: %s", user_id, exc)

    logger.info("auth/profile: updated %s for user=%s", list(updated_fields.keys()), user_id)
    return ok({"updated": updated_fields, "user_id": user_id})

