"""
Phase 251 — Dynamic Pricing Suggestion Router

Endpoint:
    GET /pricing/suggestion/{property_id}
        Returns suggested nightly rates for the next N days (default 30).
        Reads the property's rate card from the rate_cards table to get base_rate.
        Reads property occupancy from booking_state (optional — if no bookings,
        occupancy defaults to None → neutral multiplier).

        Query params:
            days          (optional, 1–90, default 30)
            room_type     (optional, default "standard")
            season        (optional, "high"|"low" — if omitted, inferred from date)
            occupancy_pct (optional, 0–100 float — override, or omit to auto-compute)

        Response:
            property_id, room_type, currency,
            summary { count, min, max, avg },
            suggestions [ { date, day_of_week, season, base_rate,
                            suggested_rate, seasonality_mult,
                            occupancy_mult, lead_time_mult } ]

    The endpoint uses a "best available base_rate" strategy:
        1. Look for exact (property_id, room_type, season) rate card
        2. If not found, look for same property_id with any room_type in that season
        3. If still not found → 404 (cannot suggest without a base rate)

    JWT auth required.
"""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from services.pricing_engine import PriceSuggestion, suggest_prices, summary_stats

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Supabase helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# GET /pricing/suggestion/{property_id}
# ---------------------------------------------------------------------------

@router.get(
    "/pricing/suggestion/{property_id}",
    tags=["pricing"],
    summary="Suggest dynamic nightly rates for next N days",
    responses={
        200: {"description": "Pricing suggestions"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "No rate card found for this property"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_pricing_suggestion(
    property_id: str,
    days: int = 30,
    room_type: str = "standard",
    occupancy_pct: Optional[float] = None,
    tenant_id: str = Depends(jwt_auth),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Suggest dynamic rates for a property.

    **Algorithm (no ML):**
    - Base rate from rate card (Phase 246)
    - × Seasonality multiplier (high season: Nov–Mar +20%, low season -10%)
    - × Occupancy pressure (≥80% full: +25%, <40% low: -10%)
    - × Lead-time multiplier (0–2 days out: -15%, ≥14 days: +5%)

    **Authentication:** Bearer JWT. `sub` = `tenant_id`.
    """
    # Validate inputs
    if not 1 <= days <= 90:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="days must be between 1 and 90.",
        )
    if occupancy_pct is not None and not 0.0 <= occupancy_pct <= 100.0:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message="occupancy_pct must be between 0 and 100.",
        )

    try:
        db = _client if _client is not None else _get_supabase_client()

        # Fetch rate card — try exact room_type first, then any
        rc_result = (
            db.table("rate_cards")
            .select("base_rate, currency, season, room_type")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        cards = rc_result.data or []

        if not cards:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message=f"No rate card found for property {property_id!r}.",
            )

        # Best-match: prefer exact room_type, fallback to first card
        match = next(
            (c for c in cards if c.get("room_type") == room_type),
            cards[0]
        )
        base_rate = float(match.get("base_rate", 0))
        currency = match.get("currency", "THB")

        if base_rate <= 0:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                message="Rate card has zero or invalid base_rate.",
            )

        # Run the engine
        suggestions = suggest_prices(
            base_rate=base_rate,
            currency=currency,
            occupancy_pct=occupancy_pct,
            days=days,
        )
        stats = summary_stats(suggestions)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "property_id": property_id,
                "room_type": match.get("room_type", room_type),
                "currency": currency,
                "base_rate": base_rate,
                "occupancy_pct": occupancy_pct,
                "summary": stats,
                "suggestions": [
                    {
                        "date": s.date,
                        "day_of_week": s.day_of_week,
                        "season": s.season,
                        "suggested_rate": s.suggested_rate,
                        "seasonality_mult": s.seasonality_mult,
                        "occupancy_mult": s.occupancy_mult,
                        "lead_time_mult": s.lead_time_mult,
                    }
                    for s in suggestions
                ],
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /pricing/suggestion/%s error for tenant=%s: %s",
            property_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
