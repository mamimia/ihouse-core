"""
Phase 194 — Booking → Guest Link

Sidecar annotation endpoints for linking / unlinking a guest identity
to a booking. Writes directly to booking_state.guest_id — NOT through
apply_envelope (this is operator reference data, not a canonical event).

Endpoints:
  POST   /bookings/{booking_id}/link-guest    Body: {"guest_id": "<uuid>"}
  DELETE /bookings/{booking_id}/link-guest    Clears -> NULL

Rules:
  - JWT auth required.
  - Tenant isolation enforced on both booking and guest lookups.
  - POST validates that both booking and guest exist for the tenant.
  - DELETE always succeeds if booking exists (idempotent unlink).
  - guest_id = null means no link; never blocks any booking operation.
  - No FK constraint in DB. Orphan protection is at API layer only.
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
# Shared: fetch booking row for tenant
# ---------------------------------------------------------------------------

def _fetch_booking(db: Any, booking_id: str, tenant_id: str) -> dict | None:
    res = (
        db.table("booking_state")
        .select("booking_id, tenant_id, status, guest_id, property_id, check_in, check_out, source")
        .eq("booking_id", booking_id)
        .eq("tenant_id", tenant_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# POST /bookings/{booking_id}/link-guest
# ---------------------------------------------------------------------------

@router.post(
    "/bookings/{booking_id}/link-guest",
    tags=["bookings", "guests"],
    summary="Link a guest identity to a booking (Phase 194)",
    responses={
        200: {"description": "Guest linked successfully"},
        400: {"description": "Missing or invalid guest_id in body"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Booking or guest not found for this tenant"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def link_guest(
    booking_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /bookings/{booking_id}/link-guest

    Body: {"guest_id": "<uuid>"}

    Validates both booking and guest exist for the tenant, then sets
    booking_state.guest_id. Direct UPDATE — not via apply_envelope.
    """
    guest_id = (body.get("guest_id") or "").strip()
    if not guest_id:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "guest_id is required"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # 1. Validate booking belongs to tenant
        booking = _fetch_booking(db, booking_id, tenant_id)
        if not booking:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"booking_id": booking_id, "detail": "Booking not found"},
            )

        # 2. Validate guest belongs to tenant (orphan protection)
        guest_res = (
            db.table("guests")
            .select("id, full_name")
            .eq("id", guest_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not (guest_res.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"guest_id": guest_id, "detail": "Guest not found for this tenant"},
            )

        guest_row = guest_res.data[0]

        # 3. Update booking_state
        db.table("booking_state").update({"guest_id": guest_id}).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "guest_id": guest_id,
                "guest_name": guest_row.get("full_name"),
                "linked": True,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /bookings/%s/link-guest error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# DELETE /bookings/{booking_id}/link-guest
# ---------------------------------------------------------------------------

@router.delete(
    "/bookings/{booking_id}/link-guest",
    tags=["bookings", "guests"],
    summary="Unlink guest identity from a booking (Phase 194)",
    responses={
        200: {"description": "Guest unlinked (guest_id set to null)"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Booking not found for this tenant"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def unlink_guest(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    DELETE /bookings/{booking_id}/link-guest

    Sets booking_state.guest_id = NULL. Idempotent — safe to call
    even if no guest was linked. Direct UPDATE, not via apply_envelope.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        booking = _fetch_booking(db, booking_id, tenant_id)
        if not booking:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"booking_id": booking_id, "detail": "Booking not found"},
            )

        db.table("booking_state").update({"guest_id": None}).eq("booking_id", booking_id).eq("tenant_id", tenant_id).execute()

        return JSONResponse(
            status_code=200,
            content={
                "booking_id": booking_id,
                "guest_id": None,
                "linked": False,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "DELETE /bookings/%s/link-guest error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
