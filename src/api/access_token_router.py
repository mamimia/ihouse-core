"""
Access Token Router — Phase 399
===================================

Admin endpoints for managing access tokens (invite + onboard).

Endpoints:
    POST /admin/access-tokens       — Issue a new token
    GET  /admin/access-tokens       — List active tokens for tenant
    POST /admin/access-tokens/revoke — Revoke a token by ID
    POST /access-tokens/validate    — Public: validate a token (for invite/onboard pages)
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from services.access_token_service import (
    TokenType,
    issue_access_token,
    record_token,
    validate_and_consume,
    revoke_token as revoke_token_by_hash,
    list_tokens,
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

class IssueTokenRequest(BaseModel):
    token_type: str = Field(..., description="'invite' or 'onboard'")
    entity_id: str = Field(..., description="Target entity (tenant_id for invite, property_id for onboard)")
    email: str = Field("", description="Recipient email")
    ttl_days: int = Field(7, ge=1, le=30, description="Token lifetime in days")
    metadata: dict = Field(default_factory=dict, description="Optional metadata")


class ValidateTokenRequest(BaseModel):
    token: str = Field(..., description="Raw access token")
    expected_type: str = Field(..., description="'invite' or 'onboard'")


class RevokeTokenRequest(BaseModel):
    token_id: str = Field(..., description="Token ID to revoke")


# ---------------------------------------------------------------------------
# Admin endpoints (JWT required)
# ---------------------------------------------------------------------------

@router.post(
    "/admin/access-tokens",
    tags=["admin"],
    summary="Issue an access token for invite or onboard (Phase 399)",
    status_code=201,
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def issue_token(
    body: IssueTokenRequest,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Issue a signed, one-use access token. Returns the raw token exactly once."""
    # Validate token_type
    try:
        tt = TokenType(body.token_type)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"error": "INVALID_TYPE", "message": f"token_type must be 'invite' or 'onboard', got '{body.token_type}'"},
        )

    try:
        raw_token, exp = issue_access_token(
            token_type=tt,
            entity_id=body.entity_id,
            email=body.email,
            ttl_seconds=body.ttl_days * 86_400,
        )
    except RuntimeError as exc:
        return JSONResponse(status_code=503, content={"error": "TOKEN_SECRET_NOT_SET", "message": str(exc)})

    # Record in DB
    db = _get_db()
    record = record_token(
        tenant_id=tenant_id,
        token_type=tt,
        entity_id=body.entity_id,
        raw_token=raw_token,
        exp=exp,
        email=body.email,
        metadata=body.metadata,
        db=db,
    )

    logger.info("access-token: issued type=%s entity=%s by tenant=%s", tt.value, body.entity_id, tenant_id)

    return JSONResponse(
        status_code=201,
        content={
            "token": raw_token,
            "token_type": tt.value,
            "entity_id": body.entity_id,
            "email": body.email,
            "expires_in_days": body.ttl_days,
            "token_id": record.get("id"),
            "expires_at": record.get("expires_at"),
        },
    )


@router.get(
    "/admin/access-tokens",
    tags=["admin"],
    summary="List active access tokens for tenant (Phase 399)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_active_tokens(
    token_type: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """List non-revoked access tokens for the authenticated tenant."""
    tt = None
    if token_type:
        try:
            tt = TokenType(token_type)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "INVALID_TYPE"})

    db = _get_db()
    tokens = list_tokens(tenant_id=tenant_id, token_type=tt, db=db)
    return JSONResponse(status_code=200, content={"tokens": tokens, "count": len(tokens)})


@router.post(
    "/admin/access-tokens/revoke",
    tags=["admin"],
    summary="Revoke an access token (Phase 399)",
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def revoke_token_endpoint(
    body: RevokeTokenRequest,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Revoke a token by its DB ID."""
    db = _get_db()

    # Look up the token hash by ID
    try:
        res = (
            db.table("access_tokens")
            .select("token_hash")
            .eq("id", body.token_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "TOKEN_NOT_FOUND"})

        token_hash = rows[0]["token_hash"]
        success = revoke_token_by_hash(token_hash=token_hash, tenant_id=tenant_id, db=db)

        if success:
            return JSONResponse(status_code=200, content={"status": "revoked", "token_id": body.token_id})
        else:
            return JSONResponse(status_code=409, content={"error": "ALREADY_REVOKED"})

    except Exception as exc:
        logger.exception("revoke error: %s", exc)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR"})


# ---------------------------------------------------------------------------
# Public endpoint (no JWT — for invite/onboard pages)
# ---------------------------------------------------------------------------

@router.post(
    "/access-tokens/validate",
    tags=["public"],
    summary="Validate an access token — public (Phase 399)",
)
async def validate_token(body: ValidateTokenRequest) -> JSONResponse:
    """
    Public endpoint. Validates a token and returns claims if valid.
    Does NOT consume the token (use the specific invite/onboard accept endpoints for that).
    """
    try:
        tt = TokenType(body.expected_type)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "INVALID_TYPE"})

    from services.access_token_service import verify_access_token

    claims = verify_access_token(body.token, expected_type=tt)
    if not claims:
        return JSONResponse(
            status_code=401,
            content={"valid": False, "error": "TOKEN_INVALID_OR_EXPIRED"},
        )

    # Check DB for revocation/usage (but don't consume)
    db = _get_db()
    token_hash = _hash_token(body.token)
    try:
        res = (
            db.table("access_tokens")
            .select("id, used_at, revoked_at, entity_id, email, metadata")
            .eq("token_hash", token_hash)
            .eq("token_type", tt.value)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return JSONResponse(status_code=401, content={"valid": False, "error": "TOKEN_NOT_FOUND"})

        row = rows[0]
        if row.get("revoked_at"):
            return JSONResponse(status_code=401, content={"valid": False, "error": "TOKEN_REVOKED"})
        if row.get("used_at"):
            return JSONResponse(status_code=401, content={"valid": False, "error": "TOKEN_ALREADY_USED"})

    except Exception:
        pass  # If DB check fails, trust HMAC

    return JSONResponse(
        status_code=200,
        content={
            "valid": True,
            "token_type": claims["token_type"],
            "entity_id": claims["entity_id"],
            "email": claims["email"],
            "metadata": row.get("metadata") if rows else {},
        },
    )
