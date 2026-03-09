"""
Phase 75 — Standardized API Error Models

Provides a shared error response helper for all API routers.

Standard error body (Phase 75+):
    {
        "code":     "BOOKING_NOT_FOUND",    ← machine-readable, SCREAMING_SNAKE_CASE
        "message":  "Booking not found ...", ← human-readable, English
        "trace_id": "uuid-from-X-Request-ID" ← correlates to logs via X-Request-ID
    }

Invariants:
  - "code" is always present and SCREAMING_SNAKE_CASE
  - "message" is present and non-empty
  - "trace_id" may be None if request_id is unavailable
  - Never leaks internal stack traces or database details in the message

Legacy note:
  financial_router and webhooks use {"error": "..."} for backward compatibility.
  New routers (bookings, admin) use this standard from Phase 75.
"""
from __future__ import annotations

from typing import Optional, Any, Dict

from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Known error codes (for discoverability)
# ---------------------------------------------------------------------------

class ErrorCode:
    BOOKING_NOT_FOUND  = "BOOKING_NOT_FOUND"
    PROPERTY_NOT_FOUND = "PROPERTY_NOT_FOUND"
    INVALID_MONTH      = "INVALID_MONTH"
    INTERNAL_ERROR     = "INTERNAL_ERROR"
    AUTH_FAILED        = "AUTH_FAILED"
    RATE_LIMITED       = "RATE_LIMITED"
    VALIDATION_ERROR   = "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Standard messages
# ---------------------------------------------------------------------------

_DEFAULT_MESSAGES: Dict[str, str] = {
    ErrorCode.BOOKING_NOT_FOUND:  "Booking not found for this tenant",
    ErrorCode.PROPERTY_NOT_FOUND: "No financial records found for this property in the requested month",
    ErrorCode.INVALID_MONTH:      "The 'month' query parameter is required and must be in YYYY-MM format",
    ErrorCode.INTERNAL_ERROR:     "An unexpected internal error occurred",
    ErrorCode.AUTH_FAILED:        "Authentication failed — missing or invalid Bearer token",
    ErrorCode.RATE_LIMITED:       "Rate limit exceeded — try again later",
    ErrorCode.VALIDATION_ERROR:   "Request payload validation failed",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def make_error_response(
    status_code: int,
    code: str,
    message: Optional[str] = None,
    trace_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """
    Create a standardized JSON error response.

    Args:
        status_code: HTTP status code (e.g. 404, 500)
        code:        machine-readable error code (SCREAMING_SNAKE_CASE)
        message:     human-readable message (defaults to built-in per code)
        trace_id:    request trace ID from X-Request-ID header (optional)
        extra:       additional fields to include in the body (e.g. booking_id)

    Returns:
        JSONResponse with standard error body
    """
    body: Dict[str, Any] = {
        "code": code,
        "message": message or _DEFAULT_MESSAGES.get(code, "An error occurred"),
    }
    if trace_id is not None:
        body["trace_id"] = trace_id
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status_code, content=body)
