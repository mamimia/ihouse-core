"""
Phase 71 — Booking State Query API

GET /bookings/{booking_id}

Returns the current state of a booking from the booking_state projection table.

Rules:
- JWT auth required (same pattern as /financial).
- Tenant isolation enforced: tenant can only read their own bookings.
  Cross-tenant reads return 404 (not 403) to avoid leaking booking existence.
- Reads from booking_state only. Never reads event_log directly.
- booking_state is a projection — its values are authoritative for read purposes,
  but the canonical source of truth remains the event_log.

Invariant (locked Phase 62+):
  This endpoint must NEVER write to booking_state or event_log.
  It is strictly a read-only projection endpoint.
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
# GET /bookings/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/bookings/{booking_id}",
    tags=["bookings"],
    summary="Get current booking state",
    responses={
        200: {"description": "Current booking state (from booking_state projection)"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Booking not found for this tenant"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_booking(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return the current state of a booking from the `booking_state` projection.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only bookings belonging to the requesting tenant are
    returned. Cross-tenant reads return 404, not 403, to avoid leaking booking
    existence information.

    **Source:** Reads from `booking_state` projection table only.
    This is the operational read model — never the canonical source of truth.
    The event_log is the canonical authority.

    **Booking status values:**
    - `active` — booking is live
    - `canceled` — booking was canceled
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_state")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
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
        return JSONResponse(
            status_code=200,
            content={
                "booking_id": row["booking_id"],
                "tenant_id": row["tenant_id"],
                "source": row.get("source"),
                "reservation_ref": row.get("reservation_ref"),
                "property_id": row.get("property_id"),
                "status": row.get("status"),
                "check_in": row.get("check_in"),
                "check_out": row.get("check_out"),
                "version": row.get("version"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /bookings/%s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
