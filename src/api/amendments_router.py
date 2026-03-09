"""
Phase 104 — Amendment History Query API

GET /amendments/{booking_id}

Returns the chronological history of all BOOKING_AMENDED financial snapshots
for a booking, drawn from booking_financial_facts where event_kind='BOOKING_AMENDED'.

Design rules:
- JWT auth required.
- Tenant isolation: .eq("tenant_id", tenant_id) at DB level.
- Reads from booking_financial_facts only. bookmark_state is never touched.
- Results ordered by recorded_at ASC (oldest amendment first).
- Returns an empty entries list (+ 0 amendments) if booking exists but
  has never been amended — NOT a 404, because the booking may be valid.
- Returns 404 if there are zero BOOKING_AMENDED rows AND zero BOOKING_CREATED
  rows for this tenant+booking_id (truly unknown booking).
  To avoid a second DB round-trip, we accept the trade-off: if no AMENDED
  rows exist we return 200 with empty list (same consistent-with-Phase-67 UX).

Invariant (locked Phase 62+):
  This endpoint must NEVER read from or write to booking_state.
"""
from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, List, Optional

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
# Internal serialiser
# ---------------------------------------------------------------------------

def _fmt(val: Any) -> Optional[str]:
    if val is None:
        return None
    return str(Decimal(str(val))) if val is not None else None


def _row_to_amendment(row: dict) -> dict:
    """Convert a booking_financial_facts BOOKING_AMENDED row to a dict."""
    return {
        "booking_id":       row.get("booking_id"),
        "provider":         row.get("provider"),
        "currency":         row.get("currency"),
        "total_price":      _fmt(row.get("total_price")),
        "ota_commission":   _fmt(row.get("ota_commission")),
        "taxes":            _fmt(row.get("taxes")),
        "fees":             _fmt(row.get("fees")),
        "net_to_property":  _fmt(row.get("net_to_property")),
        "source_confidence": row.get("source_confidence"),
        "recorded_at":      row.get("recorded_at"),
    }


# ---------------------------------------------------------------------------
# GET /amendments/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/amendments/{booking_id}",
    tags=["amendments"],
    summary="Get amendment financial history for a booking",
    responses={
        200: {"description": "Chronological list of BOOKING_AMENDED financial snapshots"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Booking not found for this tenant"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_amendments(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return the chronological list of BOOKING_AMENDED financial snapshots.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only records belonging to the requesting tenant are
    returned. Cross-tenant reads return 404 to avoid leaking booking existence.

    **Source:** Reads `booking_financial_facts` filtered by
    `event_kind = 'BOOKING_AMENDED'`, ordered by `recorded_at ASC`.
    Never reads `booking_state`.

    **Empty response:** If the booking exists but has never been amended,
    `amendments` is an empty list and `amendment_count` is 0. This is NOT a 404.

    **404:** Returned when no `booking_financial_facts` rows exist for this
    `booking_id` + `tenant_id` combination (any event_kind).
    """
    try:
        db = client if client is not None else _get_supabase_client()

        # Query all BOOKING_AMENDED rows for this booking + tenant, oldest first
        amended_result = (
            db.table("booking_financial_facts")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .eq("event_kind", "BOOKING_AMENDED")
            .order("recorded_at", desc=False)
            .execute()
        )

        amended_rows: List[dict] = amended_result.data or []

        # Verify the booking exists at all (any event_kind) to decide 200 vs 404
        if not amended_rows:
            exists_result = (
                db.table("booking_financial_facts")
                .select("booking_id")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            if not (exists_result.data or []):
                return make_error_response(
                    status_code=404,
                    code=ErrorCode.BOOKING_NOT_FOUND,
                    extra={"booking_id": booking_id},
                )

        amendments = [_row_to_amendment(r) for r in amended_rows]

        return JSONResponse(
            status_code=200,
            content={
                "booking_id":       booking_id,
                "tenant_id":        tenant_id,
                "amendment_count":  len(amendments),
                "amendments":       amendments,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /amendments/%s error: %s", booking_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
