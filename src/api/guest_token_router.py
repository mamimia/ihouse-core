"""
Guest Token Router — Phase 298
================================

Adds real (cryptographic) guest token issuance and verification
on top of the existing Phase 262 /guest/* endpoints.

New endpoints:
    POST /admin/guest-token/{booking_ref}   — Operator issues a signed token for a guest
    GET  /admin/guest-token/{booking_ref}   — Operator lists active tokens for a booking
    POST /guest/verify-token                — Guest verifies their own token (self-service)

Token format (opaque):
    base64url(booking_ref:guest_email:exp).HMAC-SHA256-sig

Security properties:
    - Tokens are signed with IHOUSE_GUEST_TOKEN_SECRET (not IHOUSE_JWT_SECRET)
    - Only the hash is stored in the DB — raw token never persisted
    - Tokens expire after 7 days (configurable per issuance)
    - Explicit revocation supported via DB (is_guest_token_revoked)
"""
from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from services.guest_token import (
    issue_guest_token,
    verify_guest_token,
    record_guest_token,
    is_guest_token_revoked,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["guest-auth"])


def _get_db():
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IssueGuestTokenRequest(BaseModel):
    guest_email: str = Field("", description="Optional guest email for audit trail")
    ttl_days: int = Field(7, ge=1, le=30, description="Token lifetime in days (1-30)")


class VerifyGuestTokenRequest(BaseModel):
    token: str = Field(..., description="Raw guest token to verify")
    booking_ref: str = Field(..., description="The booking ref being accessed")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/admin/guest-token/{booking_ref}",
    summary="Issue a signed guest token for a booking (Phase 298)",
    status_code=201,
    tags=["guest-auth"],
)
async def issue_token(
    booking_ref: str,
    body: IssueGuestTokenRequest,
    caller_id: Annotated[str, Depends(jwt_auth)],
) -> JSONResponse:
    """
    POST /admin/guest-token/{booking_ref}

    Operator issues a cryptographically signed guest access token.
    The raw token is returned exactly ONCE — only the hash is stored in the DB.
    The token should be delivered to the guest via SMS/email.

    Response includes the raw token (one-time), expiry, and token_id for management.
    """
    if not os.environ.get("IHOUSE_GUEST_TOKEN_SECRET"):
        return JSONResponse(
            status_code=503,
            content={
                "error": "GUEST_TOKEN_NOT_CONFIGURED",
                "message": "IHOUSE_GUEST_TOKEN_SECRET is not set.",
            },
        )

    ttl_seconds = body.ttl_days * 86_400
    try:
        raw_token, exp = issue_guest_token(
            booking_ref=booking_ref,
            guest_email=body.guest_email,
            ttl_seconds=ttl_seconds,
        )
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "GUEST_TOKEN_NOT_CONFIGURED", "message": str(exc)},
        )

    # Record hash in DB (best-effort)
    db = _get_db()
    record = record_guest_token(
        db=db,
        booking_ref=booking_ref,
        tenant_id=caller_id,
        raw_token=raw_token,
        exp=exp,
        guest_email=body.guest_email,
    )

    logger.info(
        "guest-token: issued for booking_ref=%s by tenant=%s email=%s",
        booking_ref, caller_id, body.guest_email,
    )

    return JSONResponse(
        status_code=201,
        content={
            "token": raw_token,       # returned exactly once
            "booking_ref": booking_ref,
            "guest_email": body.guest_email,
            "expires_in_seconds": ttl_seconds,
            "token_id": record.get("token_id"),
            "expires_at": record.get("expires_at"),
        },
    )


@router.post(
    "/guest/verify-token",
    summary="Guest self-verifies their access token (Phase 298)",
    tags=["guest-auth"],
)
async def verify_token(body: VerifyGuestTokenRequest) -> JSONResponse:
    """
    POST /guest/verify-token

    Public (no JWT) — guest submits their token + booking_ref.
    Returns 200 + token claims if valid, 401 if invalid/expired/revoked.

    Used by the Domaniqo frontend to validate a token before fetching booking data.
    """
    if not os.environ.get("IHOUSE_GUEST_TOKEN_SECRET"):
        return JSONResponse(
            status_code=503,
            content={"error": "GUEST_TOKEN_NOT_CONFIGURED",
                     "message": "IHOUSE_GUEST_TOKEN_SECRET is not set."},
        )

    try:
        claims = verify_guest_token(
            token=body.token,
            expected_booking_ref=body.booking_ref,
        )
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={"error": "GUEST_TOKEN_NOT_CONFIGURED", "message": str(exc)},
        )

    if not claims:
        # Phase 363: audit log failed verification attempts
        logger.warning(
            "guest-token: VERIFY_FAILED booking_ref=%s",
            body.booking_ref,
        )
        return JSONResponse(
            status_code=401,
            content={"valid": False, "error": "TOKEN_INVALID_OR_EXPIRED",
                     "message": "Token is invalid, expired, or does not match the booking."},
        )

    # Check DB revocation (best-effort — if DB fails, trust the HMAC)
    try:
        db = _get_db()
        if is_guest_token_revoked(db, body.token):
            logger.warning(
                "guest-token: VERIFY_REVOKED booking_ref=%s",
                body.booking_ref,
            )
            return JSONResponse(
                status_code=401,
                content={"valid": False, "error": "TOKEN_REVOKED",
                         "message": "This token has been revoked."},
            )
    except Exception:
        pass  # If DB check fails, fall through — HMAC is the primary source of truth

    # Phase 363: audit log successful verification
    logger.info(
        "guest-token: VERIFY_OK booking_ref=%s email=%s",
        claims["booking_ref"], claims.get("guest_email", ""),
    )
    return JSONResponse(
        status_code=200,
        content={
            "valid": True,
            "booking_ref": claims["booking_ref"],
            "guest_email": claims.get("guest_email", ""),
            "exp": claims["exp"],
        },
    )
