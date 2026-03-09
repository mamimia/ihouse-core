"""
Phase 103 — Payment Lifecycle Query API

GET /payment-status/{booking_id}

Returns the projected payment lifecycle state for a booking, derived
in-memory from the most recent booking_financial_facts record.
Calls project_payment_lifecycle() (Phase 93).

Rules:
- JWT auth required (same pattern as all other routers).
- Tenant isolation: only financial records for this tenant are queried.
- Reads from booking_financial_facts only. Never reads booking_state.
- In-memory projection — no DB writes, no side effects.

Invariant (locked Phase 62+):
  This endpoint must NEVER read from or write to booking_state.
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from adapters.ota.financial_extractor import (
    BookingFinancialFacts,
    CONFIDENCE_PARTIAL,
)
from adapters.ota.payment_lifecycle import explain_payment_lifecycle

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Internal: reconstruct BookingFinancialFacts from a DB row
# ---------------------------------------------------------------------------

def _row_to_facts(row: dict) -> BookingFinancialFacts:
    def _dec(val: Any) -> Optional[Decimal]:
        if val is None:
            return None
        try:
            return Decimal(str(val))
        except Exception:
            return None

    return BookingFinancialFacts(
        provider=row.get("provider", "unknown"),
        total_price=_dec(row.get("total_price")),
        currency=row.get("currency"),
        ota_commission=_dec(row.get("ota_commission")),
        taxes=_dec(row.get("taxes")),
        fees=_dec(row.get("fees")),
        net_to_property=_dec(row.get("net_to_property")),
        source_confidence=row.get("source_confidence", CONFIDENCE_PARTIAL),
        raw_financial_fields={},
    )


# ---------------------------------------------------------------------------
# GET /payment-status/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/payment-status/{booking_id}",
    tags=["payment-status"],
    summary="Get projected payment lifecycle state for a booking",
    responses={
        200: {"description": "Projected payment lifecycle state"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "No financial records found for this booking_id"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_payment_status(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return the projected payment lifecycle state for a booking.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only financial records belonging to the requesting
    tenant are returned. Cross-tenant reads return 404, not 403, to avoid
    leaking booking existence information.

    **Source:** Reads the most recent record from `booking_financial_facts`
    (ORDER BY recorded_at DESC LIMIT 1), then projects the lifecycle state
    in-memory using `project_payment_lifecycle()` (Phase 93).
    Never touches `booking_state`.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
            .limit(1)
            .execute()
        )

        if not result.data:
            return make_error_response(
                status_code=404,
                code=ErrorCode.BOOKING_NOT_FOUND,
                extra={"booking_id": booking_id},
            )

        row = result.data[0]
        facts = _row_to_facts(row)
        envelope_type = row.get("event_kind", "BOOKING_CREATED")

        # Project lifecycle state in-memory — pure, no IO
        explanation = explain_payment_lifecycle(facts, envelope_type)
        state = explanation.state

        def _fmt(val: Optional[Decimal]) -> Optional[str]:
            return str(val) if val is not None else None

        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "tenant_id": tenant_id,
                "status": state.status.value,
                "rule_applied": explanation.rule_applied,
                "reason": explanation.reason,
                "net_to_property": _fmt(state.net_to_property),
                "total_price": _fmt(state.total_price),
                "currency": state.currency,
                "source_confidence": state.source_confidence,
                "envelope_type": state.envelope_type,
                "provider": row.get("provider"),
                "recorded_at": row.get("recorded_at"),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /payment-status/%s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
