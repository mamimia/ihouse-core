"""
Phase 67 — Financial Facts Query API

GET /financial/{booking_id}

Returns the most recent financial facts for a booking from the
booking_financial_facts projection table.

Rules:
- JWT auth required (same pattern as webhooks).
- Tenant isolation enforced: tenant can only read their own bookings.
- Reads from booking_financial_facts only. Never reads booking_state.
- Most-recent row returned (ORDER BY recorded_at DESC LIMIT 1).

Invariant (locked Phase 62+):
  This endpoint must NEVER read from or write to booking_state.
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
# GET /financial/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/financial/{booking_id}",
    tags=["financial"],
    summary="Get financial facts for a booking",
    responses={
        200: {"description": "Financial facts for the booking (most recent record)"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "No financial facts found for this booking_id"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_financial_facts(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return the most recent financial facts for a given booking.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only financial records belonging to the requesting
    tenant are returned. Cross-tenant reads return 404, not 403, to avoid
    leaking booking existence information.

    **Source:** Reads from `booking_financial_facts` projection table only.
    Never touches `booking_state`.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=True)
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
                "provider": row["provider"],
                "total_price": row.get("total_price"),
                "currency": row.get("currency"),
                "ota_commission": row.get("ota_commission"),
                "taxes": row.get("taxes"),
                "fees": row.get("fees"),
                "net_to_property": row.get("net_to_property"),
                "source_confidence": row["source_confidence"],
                "event_kind": row["event_kind"],
                "recorded_at": row["recorded_at"],
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /financial/%s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
