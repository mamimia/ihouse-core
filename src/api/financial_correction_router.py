"""
Phase 162 — Financial Correction Router

POST /financial/corrections

Allows an operator to post a manual correction to booking_financial_facts.
The row is inserted with:
  - event_kind = "BOOKING_CORRECTED"
  - source_confidence = "OPERATOR_MANUAL"

An audit event is also written to event_log so the correction is traceable.

Rules:
  - JWT auth required.
  - Tenant isolation: booking must exist for the authenticated tenant.
  - Read-only validation: booking looked up from booking_state.
  - Append-only: correction rows are never updated or deleted.
  - An audit event is written to event_log best-effort (never blocks).
  - Amount fields are validated to be valid numeric strings.
  - At least one of (total_price, ota_commission, net_to_property) is required.

Body fields:
  booking_id      TEXT  required
  currency        TEXT  required  (3-letter ISO code)
  total_price     TEXT  optional  (Decimal string, e.g. "200.00")
  ota_commission  TEXT  optional
  net_to_property TEXT  optional
  taxes           TEXT  optional
  fees            TEXT  optional
  operator_note   TEXT  optional  (free-text reason for the correction)
  corrected_by    TEXT  optional  (operator username / ID)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_EVENT_KIND    = "BOOKING_CORRECTED"
_CONFIDENCE    = "OPERATOR_MANUAL"
_AMOUNT_FIELDS = frozenset({"total_price", "ota_commission", "net_to_property", "taxes", "fees"})
_REQUIRED_FIELDS = frozenset({"booking_id", "currency"})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _is_valid_decimal(value: Any) -> bool:
    """Return True if value is a string parseable as a positive-or-zero Decimal."""
    if value is None:
        return True  # optional fields may be absent
    try:
        d = Decimal(str(value))
        return d >= 0
    except (InvalidOperation, TypeError):
        return False


def _validate_body(body: dict) -> Optional[JSONResponse]:
    """Returns an error JSONResponse if the body is invalid, else None."""
    # Required keys
    for field in _REQUIRED_FIELDS:
        if not body.get(field):
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"'{field}' is required and must be non-empty."},
            )

    # currency must be 3 alpha chars
    currency = body.get("currency", "")
    if not (isinstance(currency, str) and currency.isalpha() and len(currency) == 3):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "currency must be a 3-letter ISO currency code (e.g. USD, THB)."},
        )

    # At least one amount field must be present
    if not any(field in body for field in _AMOUNT_FIELDS):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"At least one amount field is required: {sorted(_AMOUNT_FIELDS)}"},
        )

    # Validate numeric format for supplied amount fields
    for field in _AMOUNT_FIELDS:
        if field in body and not _is_valid_decimal(body[field]):
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"'{field}' must be a valid non-negative numeric string (e.g. \"200.00\")."},
            )

    return None


# ---------------------------------------------------------------------------
# POST /financial/corrections
# ---------------------------------------------------------------------------

@router.post(
    "/financial/corrections",
    tags=["financial"],
    summary="Submit an operator financial correction for a booking (Phase 162)",
    description=(
        "Inserts a new row into `booking_financial_facts` with "
        "`event_kind=BOOKING_CORRECTED` and `source_confidence=OPERATOR_MANUAL`.\\n\\n"
        "Also writes an audit event to `event_log` (best-effort).\\n\\n"
        "**Append-only:** correction rows are never modified or deleted.\\n\\n"
        "**Required fields:** `booking_id`, `currency`, and at least one amount field.\\n\\n"
        "**404** if the booking does not exist for this tenant."
    ),
    responses={
        201: {"description": "Correction row inserted successfully."},
        400: {"description": "Validation error in request body."},
        401: {"description": "Missing or invalid JWT."},
        404: {"description": "Booking not found for this tenant."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def post_financial_correction(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /financial/corrections

    Validates body, checks booking exists, inserts BOOKING_CORRECTED row,
    and writes a best-effort audit event to event_log.
    """
    # --- body validation ---
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    err = _validate_body(body)
    if err:
        return err

    booking_id = body["booking_id"].strip()
    currency   = body["currency"].strip().upper()
    now        = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = client if client is not None else _get_supabase_client()

        # --- verify booking exists for this tenant ---
        bk = (
            db.table("booking_state")
            .select("booking_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not (bk.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"booking_id": booking_id},
            )

        # --- build correction row ---
        row: dict[str, Any] = {
            "booking_id":       booking_id,
            "tenant_id":        tenant_id,
            "event_kind":       _EVENT_KIND,
            "source_confidence": _CONFIDENCE,
            "provider":         "operator",
            "currency":         currency,
        }
        for field in _AMOUNT_FIELDS:
            if field in body:
                row[field] = str(Decimal(str(body[field])))

        # Optional metadata
        if body.get("operator_note"):
            row["raw_financial_fields"] = {
                "operator_note": body["operator_note"],
                "corrected_by":  body.get("corrected_by"),
                "submitted_at":  now,
            }

        # --- insert correction row ---
        insert_result = (
            db.table("booking_financial_facts")
            .insert(row)
            .execute()
        )
        saved = (insert_result.data or [{}])[0]

        # --- best-effort audit event ---
        try:
            db.table("event_log").insert({
                "booking_id":  booking_id,
                "tenant_id":   tenant_id,
                "event_type":  "FINANCIAL_CORRECTION",
                "payload":     {
                    "corrected_fields": list(
                        f for f in _AMOUNT_FIELDS if f in body
                    ),
                    "corrected_by":     body.get("corrected_by"),
                    "operator_note":    body.get("operator_note"),
                    "currency":         currency,
                },
                "received_at": now,
            }).execute()
        except Exception:
            pass  # audit event is best-effort

        return JSONResponse(
            status_code=201,
            content={
                "status":       "inserted",
                "booking_id":   booking_id,
                "tenant_id":    tenant_id,
                "event_kind":   _EVENT_KIND,
                "confidence":   _CONFIDENCE,
                "currency":     currency,
                "corrected_fields": [f for f in _AMOUNT_FIELDS if f in body],
                "submitted_at": now,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /financial/corrections error for tenant=%s booking=%s: %s",
            tenant_id, booking_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
