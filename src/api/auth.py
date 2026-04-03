"""
JWT Authentication — FastAPI Dependency
Phase 276 — Supabase Auth JWT Integration
==========================================

Provides `verify_jwt` / `jwt_auth` — FastAPI Depends-injectable functions that:

1. Read the `Authorization: Bearer <token>` header
2. Verify the JWT against IHOUSE_JWT_SECRET (HMAC-HS256, Supabase-compatible)
3. Accept both:
   - Self-issued tokens (sub = tenant_id, from POST /auth/token)
   - Supabase Auth tokens (aud="authenticated", role="authenticated", sub = user UUID)
4. Return `tenant_id` = the `sub` claim of the validated token

Dev mode (IHOUSE_DEV_MODE=true):
    If IHOUSE_DEV_MODE is explicitly set to "true", verification is SKIPPED and
    "dev-tenant" is returned. Requires deliberate opt-in. Secret is not required.

Production mode (IHOUSE_DEV_MODE unset or false):
    IHOUSE_JWT_SECRET must be set. If absent, raises HTTP 503 (not configured).
    Missing, malformed, expired, or wrong-secret tokens raise HTTP 403.

Supabase JWT compatibility (Phase 276):
    Supabase signs tokens with the project JWT Secret (HS256). They include:
      - aud: "authenticated"
      - role: "authenticated"
      - sub: user UUID (used as tenant_id)
    Both Supabase Auth tokens and internally-issued tokens are accepted.

Environment variables:
    IHOUSE_JWT_SECRET   — HMAC-HS256 secret (Supabase project JWT secret)
    IHOUSE_DEV_MODE     — Set to "true" to skip verification (dev/test only)

Usage:
    from api.auth import jwt_auth
    from fastapi import Depends

    @router.post("/webhooks/{provider}")
    async def my_route(
        ...,
        tenant_id: str = Depends(jwt_auth),
    ): ...
"""
from __future__ import annotations

import logging
import os
from typing import Any

import jwt
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_ENV_SECRET = "IHOUSE_JWT_SECRET"
_ENV_VAR = _ENV_SECRET  # backward-compat alias (used in older tests)
_ENV_DEV_MODE = "IHOUSE_DEV_MODE"
_DEV_TENANT = os.environ.get("IHOUSE_TENANT_ID", "dev-tenant")
_ALGORITHM = "HS256"

# Supabase Auth expected claims (Phase 276)
_SUPABASE_AUD = "authenticated"
_SUPABASE_ROLE = "authenticated"


def _is_dev_mode() -> bool:
    """Return True only when IHOUSE_DEV_MODE is explicitly 'true'."""
    return os.environ.get(_ENV_DEV_MODE, "").lower().strip() == "true"


def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str:
    """
    FastAPI dependency: verifies JWT Bearer token → returns tenant_id (sub claim).

    Accepts:
      - Self-issued HS256 tokens (sub = tenant_id)
      - Supabase Auth HS256 tokens (aud="authenticated", role="authenticated", sub = user UUID)

    Args:
        credentials: Injected by FastAPI HTTPBearer security scheme.

    Returns:
        tenant_id (str) — the `sub` claim of the validated JWT.

    Raises:
        HTTPException(503): IHOUSE_JWT_SECRET not set and IHOUSE_DEV_MODE is not true.
        HTTPException(403): token missing, malformed, expired, or wrong secret.
    """
    # ------------------------------------------------------------------ #
    # Dev mode: explicit IHOUSE_DEV_MODE=true → skip, return sentinel     #
    # ------------------------------------------------------------------ #
    if _is_dev_mode():
        logger.warning(
            "JWT verification SKIPPED — IHOUSE_DEV_MODE=true. "
            "Returning '%s'. NEVER use in production.",
            _DEV_TENANT,
        )
        return _DEV_TENANT

    secret = os.environ.get(_ENV_SECRET, "")

    # ------------------------------------------------------------------ #
    # No secret and not in dev mode → auth not configured                 #
    # ------------------------------------------------------------------ #
    if not secret:
        raise HTTPException(
            status_code=503,
            detail=(
                "AUTH_NOT_CONFIGURED: IHOUSE_JWT_SECRET is not set. "
                "Set IHOUSE_DEV_MODE=true for local development."
            ),
        )

    # ------------------------------------------------------------------ #
    # Token required                                                       #
    # ------------------------------------------------------------------ #
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=403,
            detail="Missing or malformed Authorization header",
        )

    token = credentials.credentials

    # ------------------------------------------------------------------ #
    # Validate — accept both internal tokens and Supabase Auth tokens     #
    # ------------------------------------------------------------------ #
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"verify_aud": False},  # aud varies: "authenticated" vs absent
        )
    except jwt.ExpiredSignatureError:
        logger.error("JWT Error: Token has expired")
        raise HTTPException(status_code=403, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        logger.error(f"JWT Verification Failed: {exc} | Secret starts with: {secret[:4] if secret else 'NONE'}")
        raise HTTPException(status_code=403, detail=f"Invalid token: {exc}")

    # Extract tenant_id from sub claim
    sub: str | None = payload.get("sub")
    if not sub or not str(sub).strip():
        logger.error("JWT Error: Token missing sub claim")
        raise HTTPException(
            status_code=403,
            detail="Token missing 'sub' claim",
        )

    sub = str(sub).strip()

    # New format (auth_login_router): sub = user_id UUID, tenant_id in claims
    # Legacy format (session_router/dev): sub = tenant_id
    tenant_id_claim = payload.get("tenant_id")
    if tenant_id_claim:
        # New format: return tenant_id from explicit claim
        tenant_id = str(tenant_id_claim).strip()
    else:
        # Legacy format: sub IS the tenant_id
        tenant_id = sub

    # Phase 276: log Supabase Auth tokens distinctly for audit trail
    aud = payload.get("aud")
    role = payload.get("role")
    if aud == _SUPABASE_AUD or role == _SUPABASE_ROLE:
        logger.info(
            "Supabase Auth JWT accepted: sub=%s aud=%s role=%s",
            sub, aud, role,
        )

    return tenant_id


def decode_jwt_claims(token: str, secret: str) -> dict:
    """
    Decode and return all JWT claims without raising HTTPException.
    Used for introspection in /auth/supabase-verify endpoint.

    Returns empty dict on any error.
    """
    try:
        return jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
            options={"verify_aud": False},
        )
    except Exception:
        return {}


def get_identity(
    credentials: HTTPAuthorizationCredentials | None = None,
) -> dict:
    """
    Extract full identity from JWT: {user_id, tenant_id, role}.

    Supports both token formats:
      - New (auth_login_router): sub=user_id, tenant_id in claims, role in claims
      - Legacy (session_router): sub=tenant_id, role in claims, user_id=tenant_id

    Returns:
        {"user_id": str, "tenant_id": str, "role": str}

    Raises HTTPException if token is invalid.
    """
    if _is_dev_mode():
        return {
            "user_id": _DEV_TENANT,
            "tenant_id": _DEV_TENANT,
            "role": "admin",
        }

    secret = os.environ.get(_ENV_SECRET, "")
    if not secret:
        raise HTTPException(status_code=503, detail="AUTH_NOT_CONFIGURED")

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=403, detail="Missing Authorization header")

    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=[_ALGORITHM],
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        logger.error(f"Identity Verification Failed: {exc} | Secret starts with: {secret[:4] if secret else 'NONE'}")
        raise HTTPException(status_code=403, detail=f"Invalid token: {exc}")

    sub = str(payload.get("sub", "")).strip()
    if not sub:
        raise HTTPException(status_code=403, detail="Token missing 'sub' claim")

    # Detect format: new tokens have explicit tenant_id claim
    tenant_id_claim = payload.get("tenant_id")
    auth_method = str(payload.get("auth_method", "unknown")).strip()

    if tenant_id_claim:
        # New/unified format: sub=user_id, tenant_id explicit
        identity = {
            "user_id": sub,
            "tenant_id": str(tenant_id_claim).strip(),
            "role": str(payload.get("role", "manager")).strip(),
            "auth_method": auth_method,
            "email": str(payload.get("email", "")).strip(),  # Phase 864 — needed by act_as_router
            "is_active": payload.get("is_active", True),
        }

        # Phase 868 — Act As token recognition
        token_type = str(payload.get("token_type", "")).strip()
        if token_type == "act_as":
            identity["is_acting"] = True
            identity["acting_session_id"] = str(payload.get("acting_session_id", "")).strip()
            identity["real_admin_id"] = str(payload.get("real_admin_id", sub)).strip()
            identity["real_admin_email"] = str(payload.get("real_admin_email", "")).strip()
            logger.info(
                "Act As identity: admin %s (%s) acting as %s (session=%s)",
                identity["real_admin_id"],
                identity["real_admin_email"],
                identity["role"],
                identity["acting_session_id"],
            )

        return identity
    else:
        # Legacy format (pre-P22): sub=tenant_id, user_id=tenant_id
        # This branch handles tokens issued before Phase 862 P22.
        logger.debug("get_identity: legacy JWT format (no tenant_id claim) for sub=%s", sub)
        return {
            "user_id": sub,
            "tenant_id": sub,
            "role": str(payload.get("role", "manager")).strip(),
            "auth_method": "legacy",
            "is_active": payload.get("is_active", True),
        }


def _make_identity_dependency():
    """Returns a Depends-compatible callable that returns full identity dict."""
    from fastapi import Depends, Request

    async def _dep(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> dict:
        identity = get_identity(credentials)
        
        # Phase 868 — Act As tokens already carry the effective role.
        # Do not apply preview overlay on act_as sessions.
        if identity.get("is_acting"):
            # Phase 869 — Store on request.state for attribution middleware
            request.state.identity = identity
            return identity

        # Phase 847 — Admin Preview As JWT Simulation
        # Phase 866 — Enhanced: set is_preview flag for server-enforced isolation
        if identity.get("role") == "admin":
            preview_role = request.headers.get("x-preview-role")
            if preview_role:
                identity["role"] = preview_role
                identity["is_preview"] = True
                logger.info(
                    "Preview mode active: admin %s viewing as %s",
                    identity.get("user_id", "?"),
                    preview_role,
                )

        # Phase 869 — Store on request.state for attribution middleware
        request.state.identity = identity
        return identity

    return _dep


# Depends-injectable that returns {user_id, tenant_id, role}
jwt_identity = _make_identity_dependency()


def _make_simple_identity_dependency():
    """
    Returns a Depends-compatible callable that returns full identity dict.

    Identical to jwt_identity but WITHOUT the Request parameter.
    Used in role guards where the admin preview-as feature is not relevant,
    and where the Request parameter causes FastAPI/Pydantic v2 to misidentify
    it as a query field in certain dependency chain configurations.
    """
    from fastapi import Depends

    async def _dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> dict:
        return get_identity(credentials)

    return _dep


# Simpler identity dep without Request — safe for role guards / sub-dependencies
jwt_identity_simple = _make_simple_identity_dependency()


def _make_bearer_dependency():
    """
    Returns a Depends-compatible callable that chains HTTPBearer → verify_jwt.
    Used in route signatures to get both the credentials and the tenant_id.
    """
    from fastapi import Depends

    async def _dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> str:
        return verify_jwt(credentials)

    return _dep


# The canonical Depends-injectable for route use
jwt_auth = _make_bearer_dependency()


def _make_admin_only_dependency():
    """
    Phase 973 audit fix (Sonia/06 — backend closure):
    Returns a Depends-injectable that enforces admin-only access at the backend level.

    Wraps jwt_identity_simple and raises HTTP 403 CAPABILITY_DENIED if the caller's
    role is not 'admin'. Used on admin-namespace endpoints (DLQ replay, admin reporting,
    bulk operations, etc.) where only admin operators should be able to act.

    Managers (and all other roles) are rejected with a clear error message.

    Usage:
        from api.auth import admin_only_auth

        @router.post("/admin/dlq/{id}/replay")
        async def my_route(
            ...,
            identity: dict = Depends(admin_only_auth),
        ):
            tenant_id = identity["tenant_id"]
            ...
    """
    from fastapi import Depends, HTTPException

    async def _dep(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> dict:
        identity = get_identity(credentials)
        role = (identity.get("role") or "").lower()
        # Dev mode grants admin identity — allow through.
        # In production, only explicit role=admin is permitted.
        if role != "admin" and not _is_dev_mode():
            logger.warning(
                "admin_only_auth: REJECTED role=%s user_id=%s — admin role required.",
                role,
                identity.get("user_id", "unknown"),
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "CAPABILITY_DENIED",
                    "message": "This endpoint requires admin role.",
                    "required_role": "admin",
                    "caller_role": role,
                },
            )
        return identity

    return _dep


# Depends-injectable that requires role=admin — use on admin-namespace endpoints
admin_only_auth = _make_admin_only_dependency()



# ---------------------------------------------------------------------------
# Phase 165 — JWT scope enrichment helper
# ---------------------------------------------------------------------------

def get_jwt_scope(db: Any, tenant_id: str, user_id: str) -> dict:
    """
    Best-effort: look up the tenant_permissions row and return a scope dict.

    Returns:
        {
            "role":        str | None,    # 'admin' | 'manager' | 'worker' | 'owner'
            "permissions": dict,          # capability flags
        }

    Never raises. Returns empty scope if no record found or DB errors.
    Used to enrich JWT context for role-scoped endpoints (Phase 165+).

    Args:
        db:        Supabase client instance.
        tenant_id: Tenant from the JWT sub claim.
        user_id:   User identifier — typically the same as tenant_id for
                   single-user tenants, or from a 'uid' JWT claim.
    """
    from api.permissions_router import get_permission_record  # avoid circular at module level
    record = get_permission_record(db, tenant_id, user_id)
    if not record:
        return {"role": None, "permissions": {}}
    return {
        "role":        record.get("role"),
        "permissions": record.get("permissions") or {},
    }


# ---------------------------------------------------------------------------
# Phase 167 — Capability flag helpers
# ---------------------------------------------------------------------------

def get_permission_flags(
    db: Any,
    tenant_id: str,
    user_id: str,
    flags: list[str],
) -> dict[str, Any]:
    """
    Best-effort: return the requested permission flags for a user.

    Returns a dict of {flag_name: value} for each flag in `flags`.
    Missing flags get a default of None.
    Never raises — returns {flag: None, ...} on any error.
    """
    try:
        scope = get_jwt_scope(db, tenant_id, user_id)
        permissions = scope.get("permissions") or {}
        return {flag: permissions.get(flag) for flag in flags}
    except Exception:  # noqa: BLE001
        return {flag: None for flag in flags}


def has_permission(db: Any, tenant_id: str, user_id: str, flag: str) -> bool:
    """
    Best-effort: return True if the user has the given capability flag set to truthy.

    Convenience wrapper around get_permission_flags().
    Never raises — returns False on any error.
    """
    try:
        flags = get_permission_flags(db, tenant_id, user_id, [flag])
        return bool(flags.get(flag))
    except Exception:  # noqa: BLE001
        return False
