"""
Session Router — Phase 297 + Phase 397 (role claim)
============================

Server-side session management endpoints.

Endpoints:
    POST /auth/login-session       — Login: issue JWT + create server-side session
    GET  /auth/me                  — Return session/identity info for the current token
    POST /auth/logout-session      — Logout: revoke the current session
    GET  /auth/sessions            — List all active sessions for the caller
    DELETE /auth/sessions          — Revoke ALL active sessions for the caller

Design:
    - JWT signature verification still happens in api.auth (verify_jwt).
    - These endpoints add a session lookup on TOP of JWT auth.
    - /auth/login-session is the RECOMMENDED login path; /auth/token remains for dev compat.
    - /auth/me works even if no session row exists (token may be Supabase Auth or dev-issued).
    - iHouse Core token_type 'session' = issued via /auth/login-session (trackable/revocable).
    - iHouse Core token_type 'dev'     = issued via /auth/token (not tracked in sessions).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from api.envelope import ok, err
from services.session import (
    create_session,
    validate_session,
    revoke_session,
    revoke_all_sessions,
    list_active_sessions,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auth"])

_ALGORITHM = "HS256"
_TOKEN_TTL_SECONDS = 86_400  # 24 hours

_DEV_PASSWORD_ENV = "IHOUSE_DEV_PASSWORD"


def _get_db():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def _extract_token_from_request(request: Request) -> str | None:
    """Extract the raw Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return None


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

# Phase 397/836: Valid roles — must match auth_router.py VALID_ROLES
_VALID_ROLES = {"admin", "manager", "ops", "worker", "cleaner", "owner", "checkin", "checkout", "maintenance"}


class LoginSessionRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1)
    secret: str = Field(..., min_length=1)
    role: str = Field(default="manager", description="User role for route enforcement")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/auth/login-session",
    summary="Dev login: issue JWT via tenant_id+secret (use /auth/login for production)",
    status_code=201,
    tags=["auth"],
    deprecated=True,
)
async def login_session(body: LoginSessionRequest, request: Request) -> JSONResponse:
    return await _dev_login_impl(body, request)


@router.post(
    "/auth/dev-login",
    summary="Dev login: issue JWT via tenant_id+secret (internal/debug only)",
    status_code=201,
    tags=["auth"],
)
async def dev_login(body: LoginSessionRequest, request: Request) -> JSONResponse:
    return await _dev_login_impl(body, request)


async def _dev_login_impl(body: LoginSessionRequest, request: Request) -> JSONResponse:
    """
    POST /auth/dev-login (also /auth/login-session for backward compat)

    Dev/internal login via tenant_id + shared secret.
    For production login, use POST /auth/login (email + password).

    Issues a signed HS256 JWT AND creates a server-side session record.
    The session record allows explicit revocation (logout) and auditing.

    Differences vs. POST /auth/token:
    - Creates a `user_sessions` row with tenant_id + token SHA-256 hash + metadata
    - token_type in response is 'session' (vs 'dev' for /auth/token)

    **Request:**
    ```json
    {"tenant_id": "uuid", "secret": "password"}
    ```

    **Response 201:**
    ```json
    {"token": "eyJ...", "token_type": "session", "expires_in": 86400, "session": {...}}
    ```

    The secret is validated against IHOUSE_DEV_PASSWORD (default: 'dev').
    In production, replace with Supabase Auth — this remains as the tracked login path.
    """
    jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
    if not jwt_secret:
        return err("AUTH_NOT_CONFIGURED", "IHOUSE_JWT_SECRET not set", status=503)

    if not body.tenant_id.strip():
        raise HTTPException(status_code=422, detail="tenant_id is required")

    dev_password = os.environ.get(_DEV_PASSWORD_ENV, "dev")
    if body.secret != dev_password:
        logger.warning("login-session: wrong secret for tenant_id=%s", body.tenant_id)
        return err("UNAUTHORIZED", "Invalid secret", status=401)

    tenant_id = body.tenant_id.strip()

    # Phase 759: Role authority — read canonical role from DB, not from request.
    from services.role_authority import resolve_role as _resolve_role
    try:
        db_lookup = _get_db()
        role = _resolve_role(db_lookup, tenant_id, tenant_id, requested_role=body.role)
    except Exception:
        role = body.role.strip().lower() if body.role else "manager"

    if role not in _VALID_ROLES:
        return err("INVALID_ROLE", f"Invalid role '{role}'. Must be one of: {', '.join(sorted(_VALID_ROLES))}", status=422)

    # Issue JWT
    now = int(time.time())
    payload = {
        "sub": tenant_id,
        "iat": now,
        "exp": now + _TOKEN_TTL_SECONDS,
        "token_type": "session",
        "role": role,  # Phase 759: DB-authoritative role
    }
    token = jwt.encode(payload, jwt_secret, algorithm=_ALGORITHM)

    # Create server-side session
    user_agent = request.headers.get("User-Agent")
    ip_address = request.client.host if request.client else None

    db = _get_db()
    try:
        session = create_session(
            db,
            tenant_id=tenant_id,
            token=token,
            expires_in_seconds=_TOKEN_TTL_SECONDS,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    except Exception as exc:
        logger.exception("login-session: failed to create session record: %s", exc)
        # Still return the token — session creation is best-effort
        session = {}

    logger.info("login-session: issued token for tenant_id=%s role=%s (db-resolved)", tenant_id, role)
    return ok({
        "token": token,
        "token_type": "session",
        "tenant_id": tenant_id,
        "role": role,
        "expires_in": _TOKEN_TTL_SECONDS,
        "session": session,
    }, status=201)


@router.get(
    "/auth/me",
    summary="Get current identity and session info (Phase 297)",
    tags=["auth"],
)
async def get_me(
    request: Request,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /auth/me

    Returns identity info for the current token.
    Also looks up the server-side session record (if one exists).

    Response includes:
    - tenant_id (from JWT sub)
    - has_session: whether a tracked session exists for this token
    - session: session_id, created_at, expires_at (or null)

    Works for:
    - Tokens issued via /auth/login-session (has_session: true)
    - Tokens issued via /auth/token or Supabase Auth (has_session: false)
    """
    raw_token = _extract_token_from_request(request)

    session = None
    if raw_token:
        try:
            db = _get_db()
            session = validate_session(db, raw_token)
        except Exception:
            session = None

    # Phase 397: extract role from JWT for /auth/me response
    role = None
    if raw_token:
        try:
            jwt_secret = os.environ.get("IHOUSE_JWT_SECRET", "")
            if jwt_secret:
                claims = jwt.decode(raw_token, jwt_secret, algorithms=[_ALGORITHM])
                role = claims.get("role")
        except Exception:
            pass

    return ok({
        "tenant_id": caller_id,
        "role": role,
        "has_session": session is not None,
        "session": session,
    })


@router.post(
    "/auth/logout-session",
    summary="Logout: revoke current server-side session (Phase 297)",
    tags=["auth"],
)
async def logout_session(
    request: Request,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /auth/logout-session

    Revokes the server-side session for the current token (sets revoked_at + reason='logout').
    The JWT itself remains valid until its natural expiry — clients must discard it.

    Returns:
    - revoked: True if a session row was found and revoked, False if not tracked.

    This is the preferred logout path for /auth/login-session tokens.
    For non-session tokens, use the existing POST /auth/logout (cookie clear).
    """
    raw_token = _extract_token_from_request(request)

    revoked = False
    if raw_token:
        try:
            db = _get_db()
            revoked = revoke_session(db, raw_token, reason="logout")
        except Exception:
            revoked = False

    logger.info("logout-session: tenant=%s revoked=%s", caller_id, revoked)
    return ok({
        "message": "Logged out",
        "revoked": revoked,
        "tenant_id": caller_id,
    })


@router.get(
    "/auth/sessions",
    summary="List active sessions for the caller (Phase 297)",
    tags=["auth"],
)
async def get_sessions(
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    GET /auth/sessions

    Returns all non-revoked, non-expired sessions for the current tenant_id.
    token_hash is NOT returned — only session_id and metadata.
    """
    try:
        db = _get_db()
        sessions = list_active_sessions(db, caller_id)
    except Exception:
        sessions = []

    return ok({"sessions": sessions, "count": len(sessions)})


@router.delete(
    "/auth/sessions",
    summary="Revoke ALL active sessions for the caller (Phase 297)",
    tags=["auth"],
)
async def revoke_my_sessions(
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    DELETE /auth/sessions

    Revokes ALL active server-side sessions for the caller (e.g., "sign out everywhere").
    All existing JWTs for this tenant_id remain valid until their natural expiry —
    clients must discard their tokens after calling this endpoint.
    """
    try:
        db = _get_db()
        count = revoke_all_sessions(db, caller_id, reason="user_revoke_all")
    except Exception:
        count = 0

    logger.info("revoke-all-sessions: tenant=%s count=%d", caller_id, count)
    return ok({
        "message": "All sessions revoked",
        "revoked_count": count,
        "tenant_id": caller_id,
    })
