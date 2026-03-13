"""
Phase 507 — Currency Exchange API Router

Exposes the currency_service.py service (Phase 501) via HTTP endpoints.

Endpoints:
    GET  /admin/exchange-rates          — Get current exchange rates (cached or fallback)
    POST /admin/exchange-rates/refresh  — Force refresh from live API
    GET  /admin/exchange-rates/convert  — Convert amount between currencies
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["currency"])


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


@router.get(
    "/admin/exchange-rates",
    tags=["currency"],
    summary="Get current exchange rates (Phase 507)",
    responses={
        200: {"description": "Exchange rates."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_exchange_rates(
    base: str = Query(default="THB", description="Base currency"),
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    try:
        from services.currency_service import FALLBACK_RATES, fetch_live_rates
        rates = fetch_live_rates(base)
        return JSONResponse(status_code=200, content={
            "base": base,
            "rates": rates,
            "source": "live" if len(rates) > len(FALLBACK_RATES) else "fallback",
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/exchange-rates error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/admin/exchange-rates/refresh",
    tags=["currency"],
    summary="Force refresh exchange rates from live API (Phase 507)",
    responses={
        200: {"description": "Rates refreshed and cached."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def refresh_exchange_rates(
    base: str = Query(default="THB", description="Base currency"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        from services.currency_service import update_cached_rates
        db = client if client is not None else _get_supabase_client()
        result = update_cached_rates(base=base, db=db)
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/exchange-rates/refresh error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/admin/exchange-rates/convert",
    tags=["currency"],
    summary="Convert amount between currencies (Phase 507)",
    responses={
        200: {"description": "Conversion result."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def convert_currency(
    amount: float = Query(..., description="Amount to convert"),
    from_currency: str = Query(..., description="Source currency code"),
    to_currency: str = Query(..., description="Target currency code"),
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    try:
        from services.currency_service import convert
        result = convert(amount, from_currency, to_currency)
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/exchange-rates/convert error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
