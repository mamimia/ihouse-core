from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------

PROVIDER_REQUIRED       = "PROVIDER_REQUIRED"
PAYLOAD_MUST_BE_DICT    = "PAYLOAD_MUST_BE_DICT"
RESERVATION_ID_REQUIRED = "RESERVATION_ID_REQUIRED"
TENANT_ID_REQUIRED      = "TENANT_ID_REQUIRED"
OCCURRED_AT_INVALID     = "OCCURRED_AT_INVALID"
EVENT_TYPE_REQUIRED     = "EVENT_TYPE_REQUIRED"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PayloadValidationResult:
    """
    Result of an OTA payload boundary validation.

    valid  = True only when all rules pass
    errors = list of error codes (e.g. RESERVATION_ID_REQUIRED)

    Design: all errors are collected before returning (not fail-fast).
    """
    valid: bool
    errors: List[str]
    provider: str
    event_type_raw: Optional[str]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

def validate_ota_payload(
    provider: str,
    payload: Any,
) -> PayloadValidationResult:
    """
    Validate a raw OTA webhook payload at the system boundary.

    Called before normalize(). If any rule fails, the payload must not
    enter the canonical pipeline.

    Rules:
    - provider must be a non-empty string
    - payload must be a dict
    - reservation_id must be present and non-empty
    - occurred_at must be present and parseable as ISO 8601 datetime
    - at least one of event_type / type / action / event / status must be non-empty

    Note: tenant_id is no longer validated here (Phase 61).
    tenant_id is now sourced from the verified JWT token (sub claim).

    All rules are evaluated independently — multiple errors can be present.
    """
    errors: List[str] = []

    # Rule 1: provider
    if not isinstance(provider, str) or not provider.strip():
        errors.append(PROVIDER_REQUIRED)

    # Rule 2: payload must be dict
    if not isinstance(payload, dict):
        errors.append(PAYLOAD_MUST_BE_DICT)
        # Cannot evaluate field-level rules without a dict
        return PayloadValidationResult(
            valid=False,
            errors=errors,
            provider=str(provider) if provider else "",
            event_type_raw=None,
        )

    # Rule 3: reservation_id (or booking_ref for Agoda, or order_id for Trip.com)
    reservation_id = (
        payload.get("reservation_id", "") or
        payload.get("booking_ref", "") or
        payload.get("order_id", "") or
        ""
    )
    if not str(reservation_id).strip():
        errors.append(RESERVATION_ID_REQUIRED)

    # Rule 4: tenant_id — REMOVED in Phase 61.
    # tenant_id is now sourced from JWT token (sub claim), not from payload.
    # TENANT_ID_REQUIRED kept as constant for backward compatibility only.

    # Rule 5: occurred_at parseable
    occurred_at_raw = payload.get("occurred_at", None)
    if not occurred_at_raw:
        errors.append(OCCURRED_AT_INVALID)
    else:
        try:
            datetime.fromisoformat(str(occurred_at_raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            errors.append(OCCURRED_AT_INVALID)

    # Rule 6: at least one event_type field
    event_type_raw: Optional[str] = None
    for key in ("event_type", "type", "action", "event", "status"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            event_type_raw = val.strip()
            break
    if event_type_raw is None:
        errors.append(EVENT_TYPE_REQUIRED)

    return PayloadValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        provider=str(provider).strip(),
        event_type_raw=event_type_raw,
    )
