"""
Phase 132 — Booking Audit Trail

GET /bookings/{booking_id}/history

Returns a chronological audit trail for a single booking from the event_log
table. Each entry represents a discrete event in the booking's lifecycle:
BOOKING_CREATED, BOOKING_AMENDED, BOOKING_CANCELED, plus any buffered,
replayed, or DLQ events.

Response shape:
    {
        "booking_id":   str,
        "tenant_id":    str,
        "event_count":  int,
        "events": [
            {
                "event_id":     str | null,
                "event_kind":   str,
                "version":      int | null,
                "envelope_id":  str | null,
                "source":       str | null,
                "property_id":  str | null,
                "check_in":     str | null,    # YYYY-MM-DD
                "check_out":    str | null,    # YYYY-MM-DD (exclusive)
                "recorded_at":  str | null,    # ISO 8601 timestamp
            }
        ]
    }

Events are ordered chronologically ascending (oldest first).

Rules:
  - JWT auth required.
  - Tenant isolation: only events where tenant_id matches are returned.
  - Reads from event_log only. Never reads booking_state or any write table.
  - If the booking_id has no events, returns 404.
  - This endpoint is strictly read-only. Never writes to any table.

Invariant (Phase 132+):
  The event_log is the canonical source of truth. booking_state is the
  projection. This endpoint exposes the raw truth — every event, in order.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

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
# Row formatting
# ---------------------------------------------------------------------------

def _format_event(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a raw event_log row into the history event response schema.
    Only canonical, operator-visible fields are surfaced.
    Internal/implementation fields are excluded.
    """
    return {
        "event_id":    row.get("id") or row.get("event_id"),
        "event_kind":  row.get("event_kind"),
        "version":     row.get("version"),
        "envelope_id": row.get("envelope_id"),
        "source":      row.get("source"),
        "property_id": row.get("property_id"),
        "check_in":    row.get("check_in"),
        "check_out":   row.get("check_out"),
        "recorded_at": row.get("recorded_at") or row.get("created_at"),
    }


# ---------------------------------------------------------------------------
# GET /bookings/{booking_id}/history
# ---------------------------------------------------------------------------

@router.get(
    "/bookings/{booking_id}/history",
    tags=["bookings"],
    summary="Booking audit trail — full event history (Phase 132)",
    description=(
        "Returns a chronological, append-only audit trail for a single booking "
        "from the `event_log` table.\\n\\n"
        "Each entry represents one lifecycle event: `BOOKING_CREATED`, "
        "`BOOKING_AMENDED`, `BOOKING_CANCELED`, or any buffered/replayed event.\\n\\n"
        "**Ordering:** Oldest event first (`recorded_at ASC`).\\n\\n"
        "**404:** Returned when no events exist for this `booking_id` under the "
        "authenticated tenant. Cross-tenant reads return 404, not 403.\\n\\n"
        "**Source:** `event_log` only. This is the canonical source of truth — "
        "not the `booking_state` projection.\\n\\n"
        "**Invariant:** Read-only. Never writes to any table."
    ),
    responses={
        200: {"description": "Chronological event history for the booking."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "No events found for this booking_id under this tenant."},
        500: {"description": "Unexpected internal error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_booking_history(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /bookings/{booking_id}/history

    Returns all events for a booking from event_log, ordered by recorded_at ASC.
    JWT auth required.  Tenant isolation enforced at DB level.
    Reads event_log only — strictly read-only.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("event_log")
            .select(
                "id, event_id, event_kind, version, envelope_id, "
                "source, property_id, check_in, check_out, "
                "recorded_at, created_at"
            )
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .order("recorded_at", desc=False)
            .execute()
        )

        rows: List[Dict[str, Any]] = result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /bookings/%s/history error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    if not rows:
        return make_error_response(
            status_code=404,
            code=ErrorCode.BOOKING_NOT_FOUND,
            extra={"booking_id": booking_id},
        )

    events = [_format_event(r) for r in rows]

    return JSONResponse(
        status_code=200,
        content={
            "booking_id":  booking_id,
            "tenant_id":   tenant_id,
            "event_count": len(events),
            "events":      events,
        },
    )
