"""
Phase 250 — Content Push Router

Endpoints:
    POST /admin/content/push/{property_id}
        Trigger a content sync to Booking.com for a specific property.
        Body: property metadata (name, address, city, country_code, etc.)
        Supports dry_run mode.

    GET /admin/content/push/{property_id}/status
        Returns the last push result for this property from the
        content_push_log table (read-only — no retry logic here).

Design:
    - Delegates to bookingcom_content.push_property_content()
    - dry_run=True when query param ?dry_run=true (default False)
    - All writes to content_push_log (future table — currently returns inline)
    - JWT auth required.
    - Currently supports Booking.com only; adapter routing by provider
      will be added in future phases.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from adapters.outbound.bookingcom_content import PushResult, push_property_content
from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /admin/content/push/{property_id}
# ---------------------------------------------------------------------------

@router.post(
    "/admin/content/push/{property_id}",
    tags=["admin"],
    summary="Push property content to Booking.com",
    responses={
        200: {"description": "Push result (success or failure details)"},
        400: {"description": "Validation error — missing required fields"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def push_content(
    property_id: str,
    body: dict,
    dry_run: bool = False,
    tenant_id: str = Depends(jwt_auth),
    _http_client: Optional[Any] = None,
) -> JSONResponse:
    """
    Push property content fields to Booking.com Partner API.

    **Body (JSON):** property metadata for Booking.com.
    Required fields:
    - `bcom_hotel_id` or `external_id` — Booking.com hotel identifier
    - `name` — property display name
    - `address`, `city`, `country_code` — location

    Optional fields:
    - `description` (max 2000 chars)
    - `star_rating` (1-5)
    - `amenities` (list of int codes)
    - `photos` (list of URL strings)
    - `check_in_time`, `check_out_time` (HH:MM)
    - `cancellation_policy_code` (FLEX | MODERATE | STRICT | NON_REFUNDABLE)

    **Query params:**
    - `dry_run=true` — validate and build payload without sending to Booking.com

    **Authentication:** Bearer JWT. `sub` claim = `tenant_id`.
    """
    # Inject tenant and property context
    meta = {**body, "property_id": property_id, "tenant_id": tenant_id}

    try:
        result: PushResult = push_property_content(
            meta,
            dry_run=dry_run,
            _http_client=_http_client,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/content/push/%s unhandled error: %s", property_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    # Validation errors come back as success=False with an error message
    if not result.success and result.status_code is None and not result.dry_run:
        # This is a validation failure (before HTTP) — return 400
        if result.error and any(
            kw in result.error.lower()
            for kw in ("must include", "must be", "required", "invalid")
        ):
            return make_error_response(
                status_code=400,
                code="VALIDATION_ERROR",
                message=result.error,
            )

    http_status = 200
    return JSONResponse(
        status_code=http_status,
        content={
            "tenant_id": tenant_id,
            "property_id": property_id,
            "bcom_hotel_id": result.bcom_hotel_id,
            "success": result.success,
            "dry_run": result.dry_run,
            "fields_pushed": result.fields_pushed,
            "status_code": result.status_code,
            "error": result.error,
        },
    )
