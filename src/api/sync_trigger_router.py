"""
Phase 137 — Outbound Sync Trigger Router

POST /internal/sync/trigger

Given a booking_id (and optionally tenant_id override for admin use),
this endpoint:
  1. Looks up the booking from `booking_state` to get property_id + tenant_id.
  2. Fetches all enabled channel mappings from `property_channel_map`.
  3. Fetches the full provider capability registry.
  4. Calls `build_sync_plan()` to determine the outbound strategy for each channel.
  5. Returns the full sync_plan — no writes.

The plan is then passed to the Outbound Executor (Phase 138) which actually
sends API calls or iCal updates.

Response schema:
    {
        "booking_id":       "bk-airbnb-HZ001",
        "property_id":      "prop-villa-alpha",
        "tenant_id":        "tenant-001",
        "total_channels":   3,
        "api_first_count":  1,
        "ical_count":       1,
        "skip_count":       1,
        "actions": [
            {
                "provider":    "airbnb",
                "external_id": "HZ12345",
                "strategy":    "api_first",
                "reason":      "sync_mode=api_first and provider supports write API (tier=A).",
                "tier":        "A",
                "rate_limit":  120
            },
            ...
        ]
    }

Invariants:
    - JWT auth required.
    - NEVER writes to any table.
    - apply_envelope is NOT involved.
    - 404 if booking not found.
    - 200 with empty actions list if property has no channel mappings.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response
from services.outbound_sync_trigger import build_sync_plan, summarise_plan

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
# POST /internal/sync/trigger
# ---------------------------------------------------------------------------

@router.post(
    "/internal/sync/trigger",
    tags=["sync"],
    summary="Compute outbound sync plan for a booking (Phase 137)",
    description=(
        "Given a `booking_id`, computes the outbound availability sync plan "
        "by joining `property_channel_map` and `provider_capability_registry`.\\n\\n"
        "Returns a per-channel `strategy` decision:\\n"
        "- `api_first` — use the provider's write API\\n"
        "- `ical_fallback` — use iCal feed\\n"
        "- `skip` — disabled or unsupported\\n\\n"
        "**This endpoint never writes to any table.** "
        "It only produces a plan. The executor (Phase 138) applies it.\\n\\n"
        "**404** if the booking is not found.\\n"
        "**200** with an empty actions list if no channel mappings exist."
    ),
    responses={
        200: {"description": "Sync plan computed successfully."},
        400: {"description": "Invalid request body."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Booking not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def trigger_sync(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /internal/sync/trigger

    Body:
        booking_id  TEXT (required)

    Steps:
        1. Validate booking_id
        2. Lookup booking → property_id
        3. Fetch channel mappings for (tenant_id, property_id)
        4. Fetch full registry (keyed by provider)
        5. build_sync_plan()
        6. Return summarised plan
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    booking_id = body.get("booking_id")
    if not booking_id or not str(booking_id).strip():
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'booking_id' is required and must be a non-empty string."},
        )

    booking_id = str(booking_id).strip()

    try:
        db = client if client is not None else _get_supabase_client()

        # ---- Step 1: resolve property_id from booking_state ------------------
        booking_result = (
            db.table("booking_state")
            .select("property_id, tenant_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        booking_rows: List[Dict[str, Any]] = booking_result.data or []
        if not booking_rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={"detail": f"Booking '{booking_id}' not found for this tenant."},
            )

        property_id: str = booking_rows[0].get("property_id", "")

        # ---- Step 2: fetch channel mappings ----------------------------------
        channels_result = (
            db.table("property_channel_map")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        channels: List[Dict[str, Any]] = channels_result.data or []

        if not channels:
            # No mappings — return empty plan (not an error)
            return JSONResponse(
                status_code=200,
                content={
                    "booking_id":      booking_id,
                    "property_id":     property_id,
                    "tenant_id":       tenant_id,
                    "total_channels":  0,
                    "api_first_count": 0,
                    "ical_count":      0,
                    "skip_count":      0,
                    "actions":         [],
                },
            )

        # ---- Step 3: fetch provider registry ---------------------------------
        registry_result = (
            db.table("provider_capability_registry")
            .select("*")
            .execute()
        )
        registry_rows: List[Dict[str, Any]] = registry_result.data or []
        registry: Dict[str, Dict[str, Any]] = {
            row["provider"]: row for row in registry_rows if row.get("provider")
        }

        # ---- Step 4: compute sync plan ---------------------------------------
        actions = build_sync_plan(
            booking_id=booking_id,
            property_id=property_id,
            channels=channels,
            registry=registry,
        )

        plan = summarise_plan(actions)
        plan["booking_id"]  = booking_id
        plan["property_id"] = property_id
        plan["tenant_id"]   = tenant_id

        return JSONResponse(status_code=200, content=plan)

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /internal/sync/trigger error for booking=%s tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
