"""
OTA Webhook Signature Verifier
===============================

Verifies HMAC-SHA256 signatures on incoming OTA webhooks.

Each provider signs its webhook body with a shared secret.
The signature is sent as an HTTP header in the format:

    X-{Provider}-Signature: sha256=<hex_digest>

Usage:

    from adapters.ota.signature_verifier import verify_webhook_signature

    # Will raise SignatureVerificationError if invalid
    verify_webhook_signature(
        provider="airbnb",
        raw_body=request.body,      # bytes — must be the RAW body, before JSON parse
        signature_header=request.headers.get("X-Airbnb-Signature", ""),
    )

Security notes:

- Uses hmac.compare_digest() for constant-time comparison (timing attack safe)
- If secret is not configured (env var missing), verification is SKIPPED
  with a warning — this allows local dev without secrets
- If secret IS configured but signature is absent or wrong → hard failure

Environment variables:

    IHOUSE_WEBHOOK_SECRET_BOOKINGCOM
    IHOUSE_WEBHOOK_SECRET_EXPEDIA
    IHOUSE_WEBHOOK_SECRET_AIRBNB
    IHOUSE_WEBHOOK_SECRET_AGODA
    IHOUSE_WEBHOOK_SECRET_TRIPCOM
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class SignatureVerificationError(Exception):
    """
    Raised when a webhook signature is present and incorrect.
    NOT raised when the secret is unconfigured (dev mode).
    """

    def __init__(self, provider: str, reason: str) -> None:
        self.provider = provider
        self.reason = reason
        super().__init__(f"[{provider}] Signature verification failed: {reason}")


# ---------------------------------------------------------------------------
# Provider configuration
# ---------------------------------------------------------------------------

# Maps provider → (env_var_name, HTTP header name)
_PROVIDER_CONFIG: dict[str, tuple[str, str]] = {
    "bookingcom": ("IHOUSE_WEBHOOK_SECRET_BOOKINGCOM", "X-Booking-Signature"),
    "expedia":    ("IHOUSE_WEBHOOK_SECRET_EXPEDIA",    "X-Expedia-Signature"),
    "airbnb":     ("IHOUSE_WEBHOOK_SECRET_AIRBNB",     "X-Airbnb-Signature"),
    "agoda":      ("IHOUSE_WEBHOOK_SECRET_AGODA",      "X-Agoda-Signature"),
    "tripcom":    ("IHOUSE_WEBHOOK_SECRET_TRIPCOM",     "X-TripCom-Signature"),
}

_SIGNATURE_PREFIX = "sha256="


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_webhook_signature(
    provider: str,
    raw_body: bytes,
    signature_header: str,
) -> None:
    """
    Verify the HMAC-SHA256 signature of an incoming OTA webhook.

    Args:
        provider:         OTA provider name (e.g. 'airbnb')
        raw_body:         Raw bytes of the HTTP request body (BEFORE json.loads)
        signature_header: Value of the provider's signature header

    Raises:
        ValueError:                 If provider is unknown
        SignatureVerificationError: If secret is configured but signature is
                                    missing or does not match

    Returns:
        None — silent success
    """
    normalized = provider.strip().lower()

    if normalized not in _PROVIDER_CONFIG:
        raise ValueError(
            f"Unknown provider '{provider}' for signature verification. "
            f"Supported: {sorted(_PROVIDER_CONFIG.keys())}"
        )

    env_var, header_name = _PROVIDER_CONFIG[normalized]
    secret = os.environ.get(env_var, "")

    # --- Dev mode: no secret configured → skip ---
    if not secret:
        logger.warning(
            "[%s] Webhook signature verification SKIPPED — %s not set. "
            "This is expected in local/test environments.",
            provider, env_var,
        )
        return

    # --- Production mode: secret present → must verify ---
    if not signature_header:
        raise SignatureVerificationError(
            provider=provider,
            reason=f"Missing signature header '{header_name}'",
        )

    # Strip the "sha256=" prefix if present
    received_hex = signature_header.strip()
    if received_hex.startswith(_SIGNATURE_PREFIX):
        received_hex = received_hex[len(_SIGNATURE_PREFIX):]

    # Compute expected digest
    expected_hex = _compute_hmac_hex(secret=secret.encode(), body=raw_body)

    # Constant-time comparison — timing attack safe
    if not hmac.compare_digest(expected_hex, received_hex):
        raise SignatureVerificationError(
            provider=provider,
            reason="Signature mismatch — possible replay or tampering",
        )


def compute_expected_signature(provider: str, raw_body: bytes) -> str:
    """
    Compute the expected signature string for testing / generating test fixtures.

    Returns the full header value including sha256= prefix.
    Raises ValueError if the provider secret env var is not set.
    """
    normalized = provider.strip().lower()

    if normalized not in _PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider '{provider}'")

    env_var, _ = _PROVIDER_CONFIG[normalized]
    secret = os.environ.get(env_var, "")

    if not secret:
        raise ValueError(
            f"Cannot compute signature: {env_var} not set"
        )

    hex_digest = _compute_hmac_hex(secret=secret.encode(), body=raw_body)
    return f"{_SIGNATURE_PREFIX}{hex_digest}"


def get_signature_header_name(provider: str) -> str:
    """Return the HTTP header name for the given provider's signature."""
    normalized = provider.strip().lower()
    if normalized not in _PROVIDER_CONFIG:
        raise ValueError(f"Unknown provider '{provider}'")
    _, header_name = _PROVIDER_CONFIG[normalized]
    return header_name


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_hmac_hex(secret: bytes, body: bytes) -> str:
    """Compute HMAC-SHA256 and return lowercase hex string."""
    return hmac.new(secret, body, hashlib.sha256).hexdigest()
