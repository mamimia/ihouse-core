"""
Guest Token Service — Phase 298
=================================

Real cryptographic guest token generation and validation.

Replaces the stub `validate_guest_token` in services/guest_portal.py.
Tokens are HMAC-SHA256 signed, time-limited, and stored by hash in the DB.

Token format (before signing):
    <booking_ref>:<guest_email>:<exp_unix_timestamp>

Token transport:
    Opaque base64url-encoded string returned to the caller.
    Stored as SHA-256 hash only (never plaintext).

Verification:
    1. Check HMAC signature (IHOUSE_GUEST_TOKEN_SECRET)
    2. Check expiry
    3. Optionally: check DB that hash is active (not revoked)

Tables:
    guest_tokens — token_id, booking_ref, tenant_id, guest_email, token_hash, expires_at

Invariant:
    tenant_id (JWT sub) identifies the issuing operator.
    Guest tokens are scoped to (booking_ref, exp) — not to tenant_id.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_GUEST_TOKEN_ENV = "IHOUSE_GUEST_TOKEN_SECRET"
_GUEST_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_secret() -> str:
    secret = os.environ.get(_GUEST_TOKEN_ENV, "")
    if not secret:
        raise RuntimeError(
            f"IHOUSE_GUEST_TOKEN_SECRET is not set. "
            "Cannot issue or verify guest tokens."
        )
    # Phase 363: warn if secret is too short for HMAC-SHA256 (RFC 7518 §3.2)
    if len(secret) < 32:
        logger.warning(
            "IHOUSE_GUEST_TOKEN_SECRET is %d bytes, recommended minimum is 32 bytes",
            len(secret),
        )
    return secret


def _hash_token(token: str) -> str:
    """SHA-256 hex digest of the raw token string."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _make_message(booking_ref: str, guest_email: str, exp: int) -> str:
    return f"{booking_ref}:{guest_email}:{exp}"


def _sign(message: str, secret: str) -> str:
    """Return base64url-encoded HMAC-SHA256 of the message."""
    sig = hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(sig).rstrip(b"=").decode("ascii")


def _encode_token(message: str, sig: str) -> str:
    """Encode message + signature as a compact opaque token."""
    msg_b64 = base64.urlsafe_b64encode(message.encode("utf-8")).rstrip(b"=").decode("ascii")
    return f"{msg_b64}.{sig}"


def _decode_token(token: str) -> tuple[str, str] | None:
    """Decode token → (message, sig) or None on malformed input."""
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
# Token operations
# ---------------------------------------------------------------------------

def issue_guest_token(
    booking_ref: str,
    guest_email: str = "",
    ttl_seconds: int = _GUEST_TOKEN_TTL_SECONDS,
) -> tuple[str, int]:
    """
    Generate a signed guest token for a specific booking.

    Args:
        booking_ref:  The booking reference this token grants access to.
        guest_email:  Optional guest email (embedded in token for audit).
        ttl_seconds:  Token lifetime in seconds (default: 7 days).

    Returns:
        (raw_token, exp_unix_timestamp)

    Raises:
        RuntimeError if IHOUSE_GUEST_TOKEN_SECRET is not set.
    """
    secret = _get_secret()
    exp = int(time.time()) + ttl_seconds
    message = _make_message(booking_ref, guest_email, exp)
    sig = _sign(message, secret)
    raw_token = _encode_token(message, sig)
    return raw_token, exp


def verify_guest_token(
    token: str,
    expected_booking_ref: str,
) -> dict | None:
    """
    Verify a guest token.

    Returns a dict with {booking_ref, guest_email, exp} if valid.
    Returns None if:
      - Token is malformed
      - HMAC signature is invalid
      - Token has expired
      - booking_ref mismatch

    Args:
        token:                Raw token string from the guest.
        expected_booking_ref: The booking_ref being accessed.

    Raises:
        RuntimeError if IHOUSE_GUEST_TOKEN_SECRET is not set.
    """
    secret = _get_secret()

    decoded = _decode_token(token)
    if not decoded:
        return None

    message, provided_sig = decoded

    # Validate signature (constant-time compare)
    expected_sig = _sign(message, secret)
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    # Parse message
    parts = message.split(":", 2)
    if len(parts) != 3:
        return None

    booking_ref, guest_email, exp_str = parts

    # Check booking_ref match
    if booking_ref != expected_booking_ref:
        return None

    # Check expiry
    try:
        exp = int(exp_str)
    except ValueError:
        return None

    if exp < int(time.time()):
        return None

    return {
        "booking_ref": booking_ref,
        "guest_email": guest_email,
        "exp": exp,
    }


# ---------------------------------------------------------------------------
# Unified token context resolver (Phase 862 P49)
# ---------------------------------------------------------------------------

class GuestTokenContext:
    """Resolved guest token → booking + property + tenant context."""

    __slots__ = ("booking_ref", "property_id", "tenant_id", "guest_email", "exp")

    def __init__(
        self,
        booking_ref: str,
        property_id: str,
        tenant_id: str,
        guest_email: str = "",
        exp: int = 0,
    ):
        self.booking_ref = booking_ref
        self.property_id = property_id
        self.tenant_id = tenant_id
        self.guest_email = guest_email
        self.exp = exp

    def to_dict(self) -> dict:
        return {
            "booking_ref": self.booking_ref,
            "property_id": self.property_id,
            "tenant_id": self.tenant_id,
            "guest_email": self.guest_email,
            "exp": self.exp,
        }


def resolve_guest_token_context(
    token: str,
    db: Any | None = None,
) -> GuestTokenContext | None:
    """
    Canonical guest token → full context resolver.

    Steps:
        1. CI/test shortcut: tokens starting with 'test-' are accepted.
        2. Verify HMAC signature against IHOUSE_GUEST_TOKEN_SECRET.
        3. Check token expiry.
        4. Check DB revocation (best-effort).
        5. Resolve booking_ref → property_id + tenant_id from booking_state.

    Returns GuestTokenContext on success, None on any failure.
    All guest-facing endpoints MUST use this function.
    """
    # --- CI/test shortcut ---
    # SECURITY: This bypass skips HMAC verification entirely.
    # It MUST only be active in non-production environments.
    # Guard: IHOUSE_DEV_MODE=true OR IHOUSE_TEST_MODE=true must be explicitly set.
    # In production, neither variable should be set — the bypass is inert.
    _test_env_active = (
        os.environ.get("IHOUSE_DEV_MODE", "").strip().lower() == "true"
        or os.environ.get("IHOUSE_TEST_MODE", "").strip().lower() == "true"
    )
    if token.startswith("test-") and _test_env_active:
        slug = token[5:13]
        logger.warning(
            "resolve_guest_token_context: test-token shortcut used (dev/test env only). "
            "NEVER deploy with IHOUSE_DEV_MODE or IHOUSE_TEST_MODE=true in production."
        )
        return GuestTokenContext(
            booking_ref=f"BOOK-{slug}",
            property_id=f"PROP-{slug}",
            tenant_id=f"TENANT-{slug}",
        )

    # --- 1. Decode + verify HMAC ---
    try:
        secret = _get_secret()
    except RuntimeError:
        logger.warning("resolve_guest_token_context: guest token secret not configured")
        return None

    decoded = _decode_token(token)
    if not decoded:
        return None

    message, provided_sig = decoded
    expected_sig = _sign(message, secret)
    if not hmac.compare_digest(provided_sig, expected_sig):
        return None

    # --- 2. Parse message ---
    parts = message.split(":", 2)
    if len(parts) != 3:
        return None

    booking_ref, guest_email, exp_str = parts
    try:
        exp = int(exp_str)
    except ValueError:
        return None

    # --- 3. Check expiry ---
    if exp < int(time.time()):
        return None

    # --- 4. Get or create DB client ---
    if db is None:
        try:
            import os as _os
            from supabase import create_client
            db = create_client(
                _os.environ["SUPABASE_URL"],
                _os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or _os.environ["SUPABASE_KEY"],
            )
        except Exception:
            logger.warning("resolve_guest_token_context: DB unavailable, returning partial context")
            return GuestTokenContext(
                booking_ref=booking_ref,
                property_id="",
                tenant_id="",
                guest_email=guest_email,
                exp=exp,
            )

    # --- 5. Check DB revocation (best-effort) ---
    try:
        if is_guest_token_revoked(db, token):
            return None
    except Exception:
        pass  # If revocation check fails, continue with HMAC-verified data

    # --- 6. Resolve booking_ref → property_id + tenant_id ---
    property_id = ""
    tenant_id = ""
    try:
        booking_res = (
            db.table("booking_state")
            .select("property_id, tenant_id")
            .eq("booking_id", booking_ref)
            .limit(1)
            .execute()
        )
        if booking_res.data:
            row = booking_res.data[0]
            property_id = row.get("property_id", "")
            tenant_id = row.get("tenant_id", "")
    except Exception:
        logger.warning("resolve_guest_token_context: booking_state lookup failed for %s", booking_ref)

    return GuestTokenContext(
        booking_ref=booking_ref,
        property_id=property_id,
        tenant_id=tenant_id,
        guest_email=guest_email,
        exp=exp,
    )


# ---------------------------------------------------------------------------
# DB-backed token management
# ---------------------------------------------------------------------------

def record_guest_token(
    db: Any,
    booking_ref: str,
    tenant_id: str,
    raw_token: str,
    exp: int,
    guest_email: str = "",
) -> dict:
    """
    Store a guest token hash in the DB for revocation tracking.

    Args:
        db:           Supabase client (service role).
        booking_ref:  The booking_ref this token grants access to.
        tenant_id:    Issuing operator's tenant_id.
        raw_token:    The raw token (stored as hash only).
        exp:          Token expiry as Unix timestamp.
        guest_email:  Optional guest email for audit.

    Returns:
        The created guest_tokens row (without token_hash).
    """
    from datetime import datetime, timezone
    token_hash = _hash_token(raw_token)
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()

    payload = {
        "booking_ref": booking_ref,
        "tenant_id": tenant_id,
        "guest_email": guest_email,
        "token_hash": token_hash,
        "expires_at": expires_at,
    }
    try:
        res = db.table("guest_tokens").insert(payload).execute()
        row = res.data[0] if res.data else {}
        # Return without token_hash for safety
        return {k: v for k, v in row.items() if k != "token_hash"}
    except Exception as exc:
        logger.exception("record_guest_token error: %s", exc)
        return {}


def is_guest_token_revoked(db: Any, raw_token: str) -> bool:
    """
    Check if a guest token has been explicitly revoked in the DB.
    Returns False on any error or if no DB record found (token still valid by HMAC).
    """
    try:
        token_hash = _hash_token(raw_token)
        res = (
            db.table("guest_tokens")
            .select("revoked_at")
            .eq("token_hash", token_hash)
            .execute()
        )
        if not res.data:
            return False  # No record = not tracked, trust HMAC
        return res.data[0].get("revoked_at") is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Owner portal access helpers
# ---------------------------------------------------------------------------

def get_owner_properties(db: Any, owner_id: str) -> list[dict]:
    """
    Return all property_ids + roles the owner has access to (non-revoked).
    """
    try:
        res = (
            db.table("owner_portal_access")
            .select("property_id, role, granted_at")
            .eq("owner_id", owner_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return res.data or []
    except Exception as exc:
        logger.exception("get_owner_properties error: %s", exc)
        return []


def grant_owner_access(
    db: Any,
    grantor_tenant_id: str,
    owner_id: str,
    property_id: str,
    role: str = "owner",
) -> dict:
    """
    Grant an owner access to a specific property.

    Args:
        db:                Supabase client (service role).
        grantor_tenant_id: The admins tenant_id granting access.
        owner_id:          The owner's tenant_id.
        property_id:       The property being granted.
        role:              'owner' | 'viewer'

    Returns:
        The created owner_portal_access row.

    Raises:
        ValueError on invalid role or duplicate grant.
    """
    if role not in ("owner", "viewer"):
        raise ValueError(f"Invalid role '{role}'. Must be 'owner' or 'viewer'.")

    payload = {
        "tenant_id": grantor_tenant_id,
        "owner_id": owner_id,
        "property_id": property_id,
        "role": role,
        "granted_by": grantor_tenant_id,
    }
    try:
        res = db.table("owner_portal_access").insert(payload).execute()
        return res.data[0] if res.data else {}
    except Exception as exc:
        msg = str(exc)
        if "owner_portal_access_owner_id_property_id_key" in msg or "unique" in msg.lower():
            raise ValueError(f"Owner '{owner_id}' already has access to property '{property_id}'.")
        logger.exception("grant_owner_access error: %s", exc)
        raise


def has_owner_access(db: Any, owner_id: str, property_id: str) -> bool:
    """Return True if owner_id has non-revoked access to property_id."""
    try:
        res = (
            db.table("owner_portal_access")
            .select("id")
            .eq("owner_id", owner_id)
            .eq("property_id", property_id)
            .is_("revoked_at", "null")
            .execute()
        )
        return bool(res.data)
    except Exception:
        return False
