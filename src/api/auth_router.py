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

import jwt
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.envelope import ok, err

logger = logging.getLogger(__name__)

router = APIRouter()

from api.auth import jwt_auth  # noqa: E402  Phase 467

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 86_400  # 24 hours


# Valid roles for JWT role claim — controls frontend route access
VALID_ROLES = {"admin", "manager", "ops", "worker", "owner", "checkin", "checkout", "maintenance"}


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
        "sub": tenant_id,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
        "role": role,  # Phase 759: DB-authoritative role
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

        # Sign in immediately to get tokens
        signin_result = db.auth.sign_in_with_password({
            "email": body.email.strip(),
            "password": body.password,
        })

        session = signin_result.session
        logger.info("auth/signup: created user %s (%s)", user.id, body.email)
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

        logger.info("auth/signin: authenticated %s (%s)", user.id, body.email)
        return ok({
            "user_id": str(user.id),
            "email": body.email.strip(),
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_in": session.expires_in,
        })
    except Exception as exc:
        error_msg = str(exc)
        logger.warning("auth/signin: failed for %s — %s", body.email, error_msg)
        return err("AUTH_FAILED", error_msg, status=401)

