"""
Access Token Service — Phase 399
===================================

Universal access token system for invite and onboard flows.

Guest tokens remain in guest_token.py (Phase 298) — they are already production-ready.
This service handles:
    - INVITE tokens (staff invitation)
    - ONBOARD tokens (owner self-service property submission)

Token format (same as guest_token.py):
    base64url(type:entity_id:email:exp).HMAC-SHA256-sig

Security:
    - HMAC-SHA256 signed with IHOUSE_ACCESS_TOKEN_SECRET
    - Only SHA-256 hash stored in DB (never plaintext)
    - Expiry enforced at verification time
    - Revocation via DB flag
    - One-use tokens: marked used_at on first consume

Tables:
    access_tokens — id, tenant_id, token_type, entity_id, email, token_hash,
                    expires_at, used_at, revoked_at, created_at, metadata
"""
from __future__ import annotations

import base64
import hashlib
import hmac as hmac_mod
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

_TOKEN_SECRET_ENV = "IHOUSE_ACCESS_TOKEN_SECRET"
_DEFAULT_TTL_SECONDS = 7 * 24 * 3600  # 7 days


class TokenType(str, Enum):
    INVITE = "invite"
    ONBOARD = "onboard"
    STAFF_ONBOARD = "staff_onboard"


# ---------------------------------------------------------------------------
# Internal helpers (same crypto as guest_token.py)
# ---------------------------------------------------------------------------

def _get_secret() -> str:
    # Fall back to JWT secret so dev mode works without extra config
    secret = (
        os.environ.get(_TOKEN_SECRET_ENV)
        or os.environ.get("IHOUSE_JWT_SECRET")
        or ""
    )
    if not secret:
        raise RuntimeError(
            f"{_TOKEN_SECRET_ENV} (or IHOUSE_JWT_SECRET fallback) is not set. "
            "Cannot issue or verify access tokens."
        )
    return secret


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _make_message(token_type: str, entity_id: str, email: str, exp: int) -> str:
    return f"{token_type}:{entity_id}:{email}:{exp}"


def _sign(message: str, secret: str) -> str:
    sig = hmac_mod.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")


def _encode_token(message: str, sig: str) -> str:
    msg_b64 = base64.urlsafe_b64encode(message.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{msg_b64}.{sig}"


def _decode_token(token: str) -> tuple[str, str] | None:
    parts = token.split(".", 1)
    if len(parts) != 2:
        return None
    msg_b64, sig = parts
    try:
        padding = "=" * (-len(msg_b64) % 4)
        message = base64.urlsafe_b64decode(msg_b64 + padding).decode("utf-8")
        return message, sig
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Token lifecycle
# ---------------------------------------------------------------------------

def issue_access_token(
    token_type: TokenType,
    entity_id: str,
    email: str = "",
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> tuple[str, int]:
    """
    Generate a signed access token.

    Args:
        token_type: INVITE or ONBOARD
        entity_id: What this token grants access to (tenant_id for invite, property_id for onboard)
        email: Recipient email (embedded for audit)
        ttl_seconds: Lifetime in seconds

    Returns:
        (raw_token, exp_unix_timestamp)
    """
    secret = _get_secret()
    exp = int(time.time()) + ttl_seconds
    message = _make_message(token_type.value, entity_id, email, exp)
    sig = _sign(message, secret)
    raw_token = _encode_token(message, sig)
    return raw_token, exp


def verify_access_token(
    token: str,
    expected_type: TokenType | None = None,
) -> dict | None:
    """
    Verify a token's cryptographic validity.

    Returns dict with {token_type, entity_id, email, exp} if valid.
    Returns None if malformed, expired, or signature-invalid.

    Does NOT check DB revocation — caller must check separately.
    """
    secret = _get_secret()

    decoded = _decode_token(token)
    if not decoded:
        return None

    message, provided_sig = decoded

    # Validate signature (constant-time)
    expected_sig = _sign(message, secret)
    if not hmac_mod.compare_digest(provided_sig, expected_sig):
        return None

    # Parse message: type:entity_id:email:exp
    parts = message.split(":", 3)
    if len(parts) != 4:
        return None

    token_type, entity_id, email, exp_str = parts

    # Check type if expected
    if expected_type and token_type != expected_type.value:
        return None

    # Check expiry
    try:
        exp = int(exp_str)
    except ValueError:
        return None

    if exp < int(time.time()):
        return None

    return {
        "token_type": token_type,
        "entity_id": entity_id,
        "email": email,
        "exp": exp,
    }


# ---------------------------------------------------------------------------
# DB operations
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def record_token(
    tenant_id: str,
    token_type: TokenType,
    entity_id: str,
    raw_token: str,
    exp: int,
    email: str = "",
    metadata: dict | None = None,
    db: Any = None,
) -> dict:
    """
    Store token hash in access_tokens table.

    Returns the created row (without token_hash).
    """
    db = db or _get_supabase_client()
    token_hash = _hash_token(raw_token)
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()

    payload = {
        "tenant_id": tenant_id,
        "token_type": token_type.value,
        "entity_id": entity_id,
        "email": email,
        "token_hash": token_hash,
        "expires_at": expires_at,
        "metadata": metadata or {},
    }
    try:
        res = db.table("access_tokens").insert(payload).execute()
        row = res.data[0] if res.data else {}
        return {k: v for k, v in row.items() if k != "token_hash"}
    except Exception as exc:
        logger.exception("record_token error: %s", exc)
        return {}


def validate_and_consume(
    raw_token: str,
    expected_type: TokenType,
    db: Any = None,
) -> dict | None:
    """
    Full validation: HMAC + expiry + DB not-revoked + not-already-used.
    Marks the token as used_at on success.

    Returns claims dict if valid, None otherwise.
    """
    # 1. Cryptographic verification
    claims = verify_access_token(raw_token, expected_type)
    if not claims:
        return None

    # 2. DB check: not revoked, not already used
    db = db or _get_supabase_client()
    token_hash = _hash_token(raw_token)

    try:
        res = (
            db.table("access_tokens")
            .select("id, token_type, entity_id, email, used_at, revoked_at, metadata, expires_at")
            .eq("token_hash", token_hash)
            .eq("token_type", expected_type.value)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            # No DB record — token may be valid by HMAC but not tracked
            # For invite/onboard, we require DB record
            return None

        row = rows[0]
        if row.get("revoked_at"):
            return None
        if row.get("used_at"):
            return None

        # 3. Mark as used
        now = datetime.now(tz=timezone.utc).isoformat()
        db.table("access_tokens").update({
            "used_at": now,
        }).eq("id", row["id"]).execute()

        claims["db_id"] = row["id"]
        claims["metadata"] = row.get("metadata") or {}
        return claims

    except Exception as exc:
        logger.exception("validate_and_consume error: %s", exc)
        return None


def revoke_token(
    token_hash: str,
    tenant_id: str,
    db: Any = None,
) -> bool:
    """Revoke a token by its hash. Returns True if found and revoked."""
    db = db or _get_supabase_client()
    now = datetime.now(tz=timezone.utc).isoformat()
    try:
        res = (
            db.table("access_tokens")
            .update({"revoked_at": now})
            .eq("token_hash", token_hash)
            .eq("tenant_id", tenant_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return bool(res.data)
    except Exception as exc:
        logger.exception("revoke_token error: %s", exc)
        return False


def list_tokens(
    tenant_id: str,
    token_type: Optional[TokenType] = None,
    db: Any = None,
) -> list[dict]:
    """List active (non-revoked, non-expired) tokens for a tenant."""
    db = db or _get_supabase_client()
    try:
        query = (
            db.table("access_tokens")
            .select("id, token_type, entity_id, email, expires_at, used_at, created_at, metadata")
            .eq("tenant_id", tenant_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .limit(100)
        )
        if token_type:
            query = query.eq("token_type", token_type.value)
        res = query.execute()
        return res.data or []
    except Exception as exc:
        logger.exception("list_tokens error: %s", exc)
        return []
