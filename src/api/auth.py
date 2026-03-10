"""
JWT Authentication — FastAPI Dependency
========================================

Provides `verify_jwt` — a FastAPI Depends-injectable function that:

1. Reads the `Authorization: Bearer <token>` header
2. Verifies the JWT against IHOUSE_JWT_SECRET (HMAC-HS256, Supabase-compatible)
3. Returns `tenant_id` = the `sub` claim of the validated token

Dev mode:
    If IHOUSE_JWT_SECRET is not set, verification is SKIPPED and "dev-tenant"
    is returned with a warning. This allows local development without secrets.
    Identical pattern to signature_verifier.py.

Production mode:
    Secret must be set. Missing, malformed, expired, or wrong-secret tokens
    all result in HTTP 403.

Environment variables:
    IHOUSE_JWT_SECRET   — HMAC-HS256 secret (Supabase JWT secret)

Usage:
    from api.auth import verify_jwt
    from fastapi import Depends

    @router.post("/webhooks/{provider}")
    async def my_route(
        ...,
        tenant_id: str = Depends(verify_jwt),
    ): ...
"""
from __future__ import annotations

import logging
import os
from typing import Any

import jwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)

_ENV_VAR = "IHOUSE_JWT_SECRET"
_DEV_TENANT = "dev-tenant"
_ALGORITHM = "HS256"


def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = None,
) -> str:
    """
    FastAPI dependency: verifies JWT Bearer token → returns tenant_id (sub claim).

    Args:
        credentials: Injected by FastAPI HTTPBearer security scheme.

    Returns:
        tenant_id (str) — the `sub` claim of the validated JWT.

    Raises:
        HTTPException(403): token missing, malformed, expired, or wrong secret.
    """
    secret = os.environ.get(_ENV_VAR, "")

    # ------------------------------------------------------------------ #
    # Dev mode: secret not configured → skip, return sentinel tenant      #
    # ------------------------------------------------------------------ #
    if not secret:
        logger.warning(
            "JWT verification SKIPPED — %s not set. "
            "Returning '%s'. Expected in local/test environments only.",
            _ENV_VAR,
            _DEV_TENANT,
        )
        return _DEV_TENANT

    # ------------------------------------------------------------------ #
    # Production mode: secret present → must verify                       #
    # ------------------------------------------------------------------ #
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=403,
            detail="Missing or malformed Authorization header",
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token has expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=403, detail=f"Invalid token: {exc}")

    tenant_id: str | None = payload.get("sub")
    if not tenant_id or not str(tenant_id).strip():
        raise HTTPException(
            status_code=403,
            detail="Token missing 'sub' claim (tenant_id)",
        )

    return str(tenant_id).strip()


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

