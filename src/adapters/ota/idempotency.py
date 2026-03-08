from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Idempotency key format
# ---------------------------------------------------------------------------
#
# Format: "{provider}:{event_type}:{event_id}"
#
# All components are lowercased and stripped.
# Colons within components are not allowed.
#
# Examples:
#   generate_idempotency_key("bookingcom", "ev_001", "booking_created")
#   → "bookingcom:booking_created:ev_001"
#
#   generate_idempotency_key("expedia", "XID-9182", "booking_canceled")
#   → "expedia:booking_canceled:xid-9182"
#
# This ensures:
# - Cross-provider uniqueness (bookingcom ≠ expedia for same event_id)
# - Cross-type uniqueness (booking_created ≠ booking_canceled for same event_id)
# - Deterministic: same inputs always produce the same key

_VALID_KEY_PATTERN = re.compile(r"^[^:]+:[^:]+:[^:]+$")


def generate_idempotency_key(
    provider: str,
    event_id: str,
    event_type: str,
) -> str:
    """
    Generate a canonical, namespaced idempotency key for an OTA event.

    Format: "{provider}:{event_type}:{event_id}"

    All components are lowercased and stripped of leading/trailing whitespace.
    Colons within component values are replaced with underscores to prevent
    format ambiguity.

    Args:
        provider:   OTA provider name (e.g. 'bookingcom', 'expedia')
        event_id:   OTA-assigned event identifier (e.g. 'ev_001')
        event_type: canonical event type (e.g. 'BOOKING_CREATED')

    Returns:
        str — a stable, namespaced idempotency key

    Raises:
        ValueError if any component is empty after stripping
    """
    def _sanitize(value: str, label: str) -> str:
        cleaned = str(value).strip().lower().replace(":", "_")
        if not cleaned:
            raise ValueError(f"idempotency key component '{label}' must not be empty")
        return cleaned

    p = _sanitize(provider, "provider")
    t = _sanitize(event_type, "event_type")
    e = _sanitize(event_id, "event_id")

    return f"{p}:{t}:{e}"


def validate_idempotency_key(key: Optional[str]) -> bool:
    """
    Validate that a string is a properly-formed idempotency key.

    A valid key has exactly 3 colon-separated non-empty segments.

    Returns True if valid, False otherwise. Never raises.
    """
    if not key or not isinstance(key, str):
        return False
    return bool(_VALID_KEY_PATTERN.match(key.strip()))
