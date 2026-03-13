"""
Phase 506 — Financial Writer API Router

Exposes the financial_writer.py service (Phase 502) via HTTP endpoints.

Endpoints:
    POST /admin/financial/payment  — Record a manual payment or adjustment
    POST /admin/financial/payout   — Generate an owner payout record
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
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
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def record_manual_payment_endpoint(
    body: ManualPaymentRequest,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
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
    summary="Generate owner payout record (Phase 506)",
    responses={
        200: {"description": "Payout record generated."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def generate_payout_endpoint(
    body: PayoutRequest,
    tenant_id: str = Depends(jwt_auth),
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
