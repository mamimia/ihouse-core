"""
Session Service — Phase 297
==============================

Server-side session management layer.

Philosophy:
- JWT remains the transport and carries tenant_id (sub claim).
- Sessions track whether a JWT was explicitly created by a login call
  and whether it has been explicitly revoked (logout, admin action).
- Token is stored as SHA-256 hash only — never stored in plaintext.

Tables:
    user_sessions — session_id, tenant_id, token_hash, expires_at, revoked_at

Session lifecycle:
    1. Login  → create_session()  → row inserted, token_hash stored
    2. Request → validate_session() → checks hash exists + not revoked + not expired
    3. Logout  → revoke_session()  → sets revoked_at + revoked_reason

Invariant:
    tenant_id (JWT sub) is NEVER changed or re-derived here.
    This module only manages session state — auth.py still validates the JWT signature.
"""
from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS = 86_400  # 24 hours — mirrors auth_router.py


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _hash_token(token: str) -> str:
    """Return lowercase hex SHA-256 of the token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ts(dt: datetime) -> str:
    """Serialize a datetime to ISO 8601 string for Supabase."""
    return dt.isoformat()


# ---------------------------------------------------------------------------
# Session operations
# ---------------------------------------------------------------------------

def create_session(
    db: Any,
    tenant_id: str,
    token: str,
    expires_in_seconds: int = _TOKEN_TTL_SECONDS,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict:
    """
    Create a new server-side session entry.

    Args:
        db:                 Supabase client.
        tenant_id:          JWT sub claim (canonical identity).
        token:              The raw JWT string (stored as SHA-256 hash only).
        expires_in_seconds: TTL matching the JWT exp claim.
        user_agent:         Optional HTTP User-Agent for audit log.
        ip_address:         Optional client IP for audit log.

    Returns:
        dict with session_id, tenant_id, created_at, expires_at.
    """
    token_hash = _hash_token(token)
    now = _now_utc()
    expires_at = datetime.fromtimestamp(
        time.time() + expires_in_seconds, tz=timezone.utc
    )

    payload = {
        "tenant_id": tenant_id,
        "token_hash": token_hash,
        "user_agent": user_agent,
        "ip_address": ip_address,
        "expires_at": _ts(expires_at),
    }

    try:
        res = db.table("user_sessions").insert(payload).execute()
    except Exception as exc:
        logger.exception("create_session error for tenant=%s: %s", tenant_id, exc)
        raise

    row = res.data[0] if res.data else {}
    return {
        "session_id": row.get("session_id"),
        "tenant_id": row.get("tenant_id"),
        "created_at": row.get("created_at"),
        "expires_at": row.get("expires_at"),
    }


def validate_session(db: Any, token: str) -> dict | None:
    """
    Check whether a session is active for the given token.

    Returns a session dict if the session is active (not revoked, not expired).
    Returns None if:
      - No session row found for this token hash (token wasn't created via /auth/login-session)
      - Session is revoked
      - Session has expired

    NOTE: This does NOT re-verify the JWT signature (auth.py still handles that).
    This only checks the session table.

    Args:
        db:    Supabase client.
        token: The raw JWT string to look up.

    Returns:
        dict with session_id, tenant_id, created_at, expires_at — or None.
    """
    token_hash = _hash_token(token)
    now_iso = _ts(_now_utc())

    try:
        res = (
            db.table("user_sessions")
            .select("session_id, tenant_id, created_at, expires_at, revoked_at")
            .eq("token_hash", token_hash)
            .is_("revoked_at", "null")
            .execute()
        )
    except Exception as exc:
        logger.exception("validate_session error: %s", exc)
        return None

    if not res.data:
        return None

    row = res.data[0]

    # Check expiry in Python (belt-and-suspenders alongside DB view)
    expires_at = row.get("expires_at", "")
    if expires_at:
        try:
            exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if exp_dt < _now_utc():
                return None
        except ValueError:
            pass

    return {
        "session_id": row.get("session_id"),
        "tenant_id": row.get("tenant_id"),
        "created_at": row.get("created_at"),
        "expires_at": row.get("expires_at"),
    }


def revoke_session(
    db: Any,
    token: str,
    reason: str = "logout",
) -> bool:
    """
    Revoke a session by token hash.

    Args:
        db:     Supabase client.
        token:  The raw JWT string to revoke.
        reason: 'logout' | 'admin' | 'expired'

    Returns:
        True if a session was revoked, False if not found.
    """
    token_hash = _hash_token(token)
    now_iso = _ts(_now_utc())

    try:
        res = (
            db.table("user_sessions")
            .update({"revoked_at": now_iso, "revoked_reason": reason})
            .eq("token_hash", token_hash)
            .is_("revoked_at", "null")
            .execute()
        )
    except Exception as exc:
        logger.exception("revoke_session error: %s", exc)
        return False

    return bool(res.data)


def revoke_all_sessions(db: Any, tenant_id: str, reason: str = "admin") -> int:
    """
    Revoke ALL active sessions for a tenant_id.

    Args:
        db:        Supabase client.
        tenant_id: The tenant whose sessions to revoke.
        reason:    Revocation reason tag.

    Returns:
        Number of sessions revoked.
    """
    now_iso = _ts(_now_utc())
    try:
        res = (
            db.table("user_sessions")
            .update({"revoked_at": now_iso, "revoked_reason": reason})
            .eq("tenant_id", tenant_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return len(res.data or [])
    except Exception as exc:
        logger.exception("revoke_all_sessions error for tenant=%s: %s", tenant_id, exc)
        return 0


def list_active_sessions(db: Any, tenant_id: str) -> list[dict]:
    """
    Return all active (non-revoked, non-expired) sessions for a tenant.

    Note: token_hash is NOT returned — session_id only for management.
    """
    try:
        res = (
            db.table("user_sessions")
            .select("session_id, tenant_id, user_agent, ip_address, created_at, expires_at")
            .eq("tenant_id", tenant_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
            .execute()
        )
        now = _now_utc()
        return [
            row for row in (res.data or [])
            if _is_not_expired(row.get("expires_at", ""), now)
        ]
    except Exception as exc:
        logger.exception("list_active_sessions error for tenant=%s: %s", tenant_id, exc)
        return []


def _is_not_expired(expires_at_str: str, now: datetime) -> bool:
    """Return True if the session has not yet expired."""
    if not expires_at_str:
        return False
    try:
        exp_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        return exp_dt > now
    except ValueError:
        return False
