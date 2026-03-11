"""
Phase 246 — Rate Card & Pricing Rules Engine

Endpoints:
    GET  /properties/{property_id}/rate-cards
        List all rate cards for a property (tenant-scoped).

    POST /properties/{property_id}/rate-cards
        Create or update a rate card for a (room_type, season, currency) combo.
        Upsert semantics: if a card already exists for the (tenant, property,
        room_type, season) combination the base_rate and currency are updated.

    GET  /properties/{property_id}/rate-cards/check
        Check whether a given booking price deviates from the rate card.
        Query params: price (float), currency, room_type (optional),
                      season (optional), check_in_month (optional 1-12).

Invariants:
    - All reads/writes scoped to tenant_id from JWT sub claim.
    - Reads only rate_cards table via Supabase client.
    - Writes use upsert on the unique constraint (tenant, property, room_type, season).
    - Price deviation check is pure Python — no DB writes.
    - JWT auth required on all endpoints.
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
from services.price_deviation_detector import check_price_deviation

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /properties/{property_id}/rate-cards
# ---------------------------------------------------------------------------

@router.get(
    "/properties/{property_id}/rate-cards",
    tags=["properties"],
    summary="List rate cards for a property",
    responses={
        200: {"description": "List of rate cards for this property"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_rate_cards(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return all rate cards for the specified property.

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    try:
        db = _client if _client is not None else _get_supabase_client()
        result = (
            db.table("rate_cards")
            .select("id, property_id, room_type, season, base_rate, currency, created_at, updated_at")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("room_type")
            .execute()
        )
        cards = result.data or []
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "property_id": property_id,
                "count": len(cards),
                "rate_cards": cards,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /properties/%s/rate-cards error: %s", property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /properties/{property_id}/rate-cards
# ---------------------------------------------------------------------------

@router.post(
    "/properties/{property_id}/rate-cards",
    tags=["properties"],
    summary="Create or update a rate card for a property",
    status_code=201,
    responses={
        201: {"description": "Rate card created or updated"},
        400: {"description": "Validation error — missing or invalid fields"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_rate_card(
    property_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Create or update a rate card.

    **Body (JSON):**
    - `room_type` *(required)* — room type identifier (e.g. "standard", "deluxe")
    - `season` *(required)* — season label (e.g. "high", "low", "shoulder")
    - `base_rate` *(required)* — base price per night (numeric, ≥ 0)
    - `currency` *(optional, default "THB")* — ISO currency code

    **Upsert rule:** if a card already exists for the same
    `(tenant_id, property_id, room_type, season)`, the `base_rate` and
    `currency` are updated. Otherwise a new record is created.

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    # Validate required fields
    room_type = body.get("room_type")
    season = body.get("season")
    base_rate_raw = body.get("base_rate")
    currency = (body.get("currency") or "THB").upper().strip()

    if not room_type or not season:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="room_type and season are required.",
        )

    try:
        base_rate = Decimal(str(base_rate_raw))
        if base_rate < Decimal("0"):
            raise ValueError("negative")
    except Exception:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="base_rate must be a non-negative number.",
        )

    try:
        db = _client if _client is not None else _get_supabase_client()

        # Upsert by the unique constraint
        row = {
            "tenant_id": tenant_id,
            "property_id": property_id,
            "room_type": room_type,
            "season": season,
            "base_rate": str(base_rate),
            "currency": currency,
        }

        # Try insert first; on conflict (unique key), update base_rate + currency
        result = (
            db.table("rate_cards")
            .upsert(row, on_conflict="tenant_id,property_id,room_type,season")
            .execute()
        )
        saved = result.data[0] if result.data else row

        return JSONResponse(
            status_code=201,
            content={
                "tenant_id": tenant_id,
                "property_id": property_id,
                "rate_card": saved,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /properties/%s/rate-cards error: %s", property_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /properties/{property_id}/rate-cards/check
# ---------------------------------------------------------------------------

@router.get(
    "/properties/{property_id}/rate-cards/check",
    tags=["properties"],
    summary="Check if a booking price deviates from the rate card (±15% threshold)",
    responses={
        200: {"description": "Price deviation check result"},
        400: {"description": "Validation error"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def check_rate_card_deviation(
    property_id: str,
    price: Optional[float] = None,
    currency: str = "THB",
    room_type: Optional[str] = None,
    season: Optional[str] = None,
    check_in_month: Optional[int] = None,
    booking_id: str = "adhoc",
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Check if a given `price` deviates from the matching rate card by more than 15%.

    **Query parameters:**
    - `price` *(required)* — incoming booking price per night
    - `currency` *(optional, default "THB")* — currency of the price
    - `room_type` *(optional)* — narrow matching to a specific room type
    - `season` *(optional)* — explicit season override ("high" | "low")
    - `check_in_month` *(optional, 1-12)* — used for automatic season inference
    - `booking_id` *(optional)* — for traceability

    **Returns:**
    - `alert: true` if deviation > 15% from rate card
    - `deviation_pct` — deviation in percent
    - `direction` — "above" or "below"
    - `no_rate_card: true` if no matching rate card was found

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    if price is None:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="price query parameter is required.",
        )

    try:
        incoming = Decimal(str(price))
    except Exception:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="price must be a valid number.",
        )

    try:
        db = _client if _client is not None else _get_supabase_client()
        result = (
            db.table("rate_cards")
            .select("room_type, season, base_rate, currency")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        cards = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /properties/%s/rate-cards/check error: %s", property_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    dev = check_price_deviation(
        booking_id=booking_id,
        property_id=property_id,
        incoming_price=incoming,
        currency=currency.upper(),
        rate_cards=cards,
        room_type=room_type,
        season=season,
        check_in_month=check_in_month,
    )

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "property_id": property_id,
            "booking_id": dev.booking_id,
            "no_rate_card": dev.no_rate_card,
            "alert": dev.alert,
            "incoming_price": str(dev.incoming_price),
            "base_rate": str(dev.base_rate) if dev.base_rate is not None else None,
            "currency": dev.currency,
            "season": dev.season,
            "room_type": dev.room_type,
            "deviation_pct": str(dev.deviation_pct) if dev.deviation_pct is not None else None,
            "direction": dev.direction,
        },
    )
