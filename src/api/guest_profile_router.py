"""
Phase 159 — Guest Profile Router

GET /bookings/{booking_id}/guest-profile

Returns extracted PII (guest name, email, phone) for a booking.
Data is sourced from the `guest_profile` table (never event_log).

Rules:
  - JWT auth required.
  - Tenant isolation: only data for the authenticated tenant is returned.
  - 404 returned if booking exists but no guest profile has been extracted yet.
  - 404 returned for cross-tenant requests (no 403 to avoid existence leak).
  - Read-only. Never writes to any table.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

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
# GET /bookings/{booking_id}/guest-profile
# ---------------------------------------------------------------------------

@router.get(
    "/bookings/{booking_id}/guest-profile",
    tags=["bookings", "guest"],
    summary="Retrieve extracted guest profile for a booking (Phase 159)",
    description=(
        "Returns the canonical guest profile (name, email, phone) extracted from "
        "the OTA webhook payload at booking creation time.\\n\\n"
        "**Source:** `guest_profile` table only. Never reads `event_log`.\\n\\n"
        "**404** if no guest profile exists for this booking + tenant.\\n\\n"
        "**PII note:** This endpoint returns PII. Ensure appropriate access control."
    ),
    responses={
        200: {"description": "Guest profile for the booking."},
        401: {"description": "Missing or invalid JWT."},
        404: {"description": "No guest profile found for this booking."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_guest_profile(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /bookings/{booking_id}/guest-profile

    Retrieves the guest profile from the `guest_profile` table.
    Tenant-scoped — cross-tenant reads return 404.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("guest_profile")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )

        if not (result.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={
                    "booking_id": booking_id,
                    "detail": "No guest profile found for this booking.",
                },
            )

        row = result.data[0]
        return JSONResponse(
            status_code=200,
            content={
                "booking_id":  row.get("booking_id"),
                "tenant_id":   row.get("tenant_id"),
                "guest_name":  row.get("guest_name"),
                "guest_email": row.get("guest_email"),
                "guest_phone": row.get("guest_phone"),
                "source":      row.get("source"),
                "created_at":  row.get("created_at"),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /bookings/%s/guest-profile error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
