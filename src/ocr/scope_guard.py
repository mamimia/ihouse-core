"""
Phase 982 — OCR Scope Guard
=============================

The sole enforcer of OCR scope boundaries.

INVARIANT (INV-OCR-01):
    OCR ONLY runs for capture_type in the ALLOWED set.
    No exceptions. No overrides. No admin bypass.

Any attempt to process OCR for a non-allowed capture type
raises OcrScopeViolation. This is not a 400 — it's a hard
invariant violation that must never reach producer code.
"""
from __future__ import annotations

import logging
from typing import FrozenSet

logger = logging.getLogger(__name__)


# ─── LOCKED SCOPE ───────────────────────────────────────────────────
# Changing this set requires a deliberate product decision.
# Do NOT add capture types without explicit approval.
# ────────────────────────────────────────────────────────────────────

ALLOWED_CAPTURE_TYPES: FrozenSet[str] = frozenset({
    "identity_document_capture",
    "checkin_opening_meter_capture",
    "checkout_closing_meter_capture",
})


class OcrScopeViolation(Exception):
    """Raised when OCR is requested for a capture_type outside the allowed scope."""

    def __init__(self, capture_type: str) -> None:
        self.capture_type = capture_type
        super().__init__(
            f"OCR scope violation: capture_type '{capture_type}' is not allowed. "
            f"Allowed types: {sorted(ALLOWED_CAPTURE_TYPES)}"
        )


def validate_capture_type(capture_type: str) -> str:
    """
    Validate that a capture_type is in the allowed OCR scope.

    Args:
        capture_type: The capture type identifier from the request.

    Returns:
        The validated capture_type (normalized, stripped).

    Raises:
        OcrScopeViolation: If capture_type is not in the allowed set.
    """
    normalized = (capture_type or "").strip().lower()

    if not normalized:
        raise OcrScopeViolation("<empty>")

    if normalized not in ALLOWED_CAPTURE_TYPES:
        logger.warning(
            "OCR scope guard BLOCKED: capture_type='%s' not in allowed set %s",
            capture_type,
            sorted(ALLOWED_CAPTURE_TYPES),
        )
        raise OcrScopeViolation(capture_type)

    logger.debug("OCR scope guard PASSED: capture_type='%s'", normalized)
    return normalized


def is_allowed(capture_type: str) -> bool:
    """
    Check if a capture_type is in the allowed OCR scope.

    Non-raising version of validate_capture_type.
    Returns False for empty/invalid types.
    """
    normalized = (capture_type or "").strip().lower()
    return normalized in ALLOWED_CAPTURE_TYPES


# ─── Helpers for categorizing capture types ─────────────────────────

def is_identity_capture(capture_type: str) -> bool:
    """True if this capture type is for identity document OCR."""
    return (capture_type or "").strip().lower() == "identity_document_capture"


def is_meter_capture(capture_type: str) -> bool:
    """True if this capture type is for electricity meter OCR."""
    normalized = (capture_type or "").strip().lower()
    return normalized in {
        "checkin_opening_meter_capture",
        "checkout_closing_meter_capture",
    }


def get_meter_reading_type(capture_type: str) -> str | None:
    """
    For meter captures, return 'opening' or 'closing'.
    Returns None if not a meter capture.
    """
    normalized = (capture_type or "").strip().lower()
    if normalized == "checkin_opening_meter_capture":
        return "opening"
    elif normalized == "checkout_closing_meter_capture":
        return "closing"
    return None
