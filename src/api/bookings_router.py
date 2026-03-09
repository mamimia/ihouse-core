"""
Phase 71 — Booking State Query API
Phase 106 — Booking List Query API

GET /bookings/{booking_id}    — single booking state (Phase 71)
GET /bookings                 — list bookings by tenant, with filters (Phase 106)

Rules:
- JWT auth required on both endpoints.
- Tenant isolation enforced at DB level (.eq("tenant_id", tenant_id)).
- Reads from booking_state only. Never reads event_log directly.
- booking_state is a projection — its values are authoritative for read purposes,
  but the canonical source of truth remains the event_log.

Invariant (locked Phase 62+):
  These endpoints must NEVER write to booking_state or event_log.
  Strictly read-only projection endpoints.
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


# ---------------------------------------------------------------------------
# GET /bookings (Phase 106)
# ---------------------------------------------------------------------------

_VALID_STATUSES = frozenset({"active", "canceled"})
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


@router.get(
    "/bookings",
    tags=["bookings"],
    summary="List bookings for a tenant",
    responses={
        200: {"description": "Paginated list of bookings from booking_state projection"},
        400: {"description": "Invalid query parameter (e.g. unknown status value)"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_bookings(
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return a paginated list of bookings from the `booking_state` projection.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** All results are scoped to the authenticated tenant.

    **Query parameters:**
    - `property_id` — filter by property (optional)
    - `status` — filter by booking status: `active` or `canceled` (optional)
    - `limit` — max results to return (1–100, default 50)

    **Source:** Reads from `booking_state` projection table only.
    Never reads `event_log` directly.

    **Invariant:** Read-only. Never writes to any table.
    """
    # Validate status
    if status is not None and status not in _VALID_STATUSES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"status must be one of: {sorted(_VALID_STATUSES)}"},
        )

    # Clamp limit
    limit = max(1, min(limit, _MAX_LIMIT))

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("booking_state")
            .select("*")
            .eq("tenant_id", tenant_id)
        )

        if property_id is not None:
            query = query.eq("property_id", property_id)

        if status is not None:
            query = query.eq("status", status)

        result = query.limit(limit).order("updated_at", desc=True).execute()
        rows = result.data or []

        bookings = [
            {
                "booking_id":      r["booking_id"],
                "tenant_id":       r["tenant_id"],
                "source":          r.get("source"),
                "reservation_ref": r.get("reservation_ref"),
                "property_id":     r.get("property_id"),
                "status":          r.get("status"),
                "check_in":        r.get("check_in"),
                "check_out":       r.get("check_out"),
                "version":         r.get("version"),
                "created_at":      r.get("created_at"),
                "updated_at":      r.get("updated_at"),
            }
            for r in rows
        ]

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":     tenant_id,
                "count":         len(bookings),
                "limit":         limit,
                "bookings":      bookings,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /bookings error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

