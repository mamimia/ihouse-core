"""
Phase 506 — Financial Writer API Router

Exposes the financial_writer.py service (Phase 502) via HTTP endpoints.

Endpoints:
    POST /admin/financial/payment  — Record a manual payment or adjustment
    POST /admin/financial/payout   — Generate an owner payout record

Authorization:
    Both endpoints require the "financial" capability via require_capability().
    This means:
      - admin role       → always allowed
      - manager role     → allowed only if "financial" capability is delegated
      - all other roles  → HTTP 403 CAPABILITY_DENIED

    Matching the guard pattern used in financial_router.py (read side).
    The write side must be at least as protected as the read side.

Actor attribution:
    record_manual_payment() now receives the real user_id from jwt_identity
    so the admin_audit_log entry records who made the change instead of
    the anonymizing hardcoded string "frontend".
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth, jwt_identity
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["financial-writer"])


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


class ManualPaymentRequest(BaseModel):
    booking_id: str = Field(..., description="Target booking ID")
    amount: float = Field(..., description="Payment amount")
    currency: str = Field(default="THB", description="Currency code")
    payment_type: str = Field(default="manual_adjustment", description="Payment type")
    notes: str = Field(default="", description="Free-text notes")


class PayoutRequest(BaseModel):
    property_id: str = Field(..., description="Property ID")
    period_start: str = Field(..., description="Period start (YYYY-MM-DD)")
    period_end: str = Field(..., description="Period end (YYYY-MM-DD)")
    mgmt_fee_pct: float = Field(default=15.0, description="Management fee percentage")


@router.post(
    "/admin/financial/payment",
    tags=["financial-writer"],
    summary="Record manual payment or adjustment (Phase 506)",
    responses={
        200: {"description": "Payment recorded."},
        401: {"description": "Missing or invalid JWT."},
        403: {"description": "CAPABILITY_DENIED — requires financial capability."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def record_manual_payment_endpoint(
    body: ManualPaymentRequest,
    tenant_id: str = Depends(jwt_auth),
    identity: dict = Depends(jwt_identity),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    # Real actor_id from the JWT — preserves audit accountability
    actor_id = identity.get("user_id") or tenant_id
    try:
        from services.financial_writer import record_manual_payment

        db = client if client is not None else _get_supabase_client()
        result = record_manual_payment(
            db=db,
            tenant_id=tenant_id,
            booking_id=body.booking_id,
            amount=body.amount,
            currency=body.currency,
            payment_type=body.payment_type,
            notes=body.notes,
            actor_id=actor_id,
        )
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/financial/payment error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/admin/financial/payout",
    tags=["financial-writer"],
    # ACCURACY NOTE: This endpoint calculates a payout — it does NOT persist it.
    # "Generate owner payout calculation" is the accurate description.
    # The response includes a payout_id and status="calculated" to indicate
    # this is a point-in-time snapshot, not a committed payout record.
    # Full payout persistence is a deferred feature (no payouts table exists yet).
    summary="Calculate owner payout (Phase 506 — calculation only, not persisted)",
    responses={
        200: {"description": "Payout calculation returned (NOT persisted — session reference only)."},
        401: {"description": "Missing or invalid JWT."},
        403: {"description": "CAPABILITY_DENIED — requires financial capability."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def generate_payout_endpoint(
    body: PayoutRequest,
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("financial")),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        from services.financial_writer import generate_payout_record

        db = client if client is not None else _get_supabase_client()
        result = generate_payout_record(
            db=db,
            tenant_id=tenant_id,
            property_id=body.property_id,
            period_start=body.period_start,
            period_end=body.period_end,
            mgmt_fee_pct=body.mgmt_fee_pct,
        )
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/financial/payout error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
