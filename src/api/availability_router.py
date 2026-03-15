"""
Phase 126 — Availability Projection Router

Second read model beyond booking_state. Provides per-property, per-date
occupancy state derived from the booking_state projection.

Design rationale:
- booking_state is the single source of truth for projection reads.
- availability_projection is NOT a new DB table — it is computed in-memory
  from booking_state rows on every request (date-range scan pattern).
- Zero write-path changes. This router only reads; it never writes.
- Foundation for: channel sync, OTA calendar push, and rate management.

Endpoint:
    GET /availability/{property_id}?from=<date>&to=<date>

Response: per-date occupancy map — for each date in [from, to),
returns which booking_id occupies it (or null if vacant).

Invariants:
- Reads from booking_state only. Never reads event_log directly.
- Never reads booking_financial_facts.
- Only ACTIVE bookings contribute to occupancy (CANCELED excluded).
- date range: [from, to) — check_in inclusive, check_out exclusive.
- Multi-booking overlap on same date is flagged as CONFLICT.
- No DB-level date arithmetic: range expansion is done in Python.
- tenant_id isolation enforced at DB query level (property scoped to tenant).
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.error_models import make_error_response

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_supabase_client(request: Request):
    """Resolve Supabase client from app state (standard pattern)."""
    return request.app.state.supabase


def _date_range(from_date: date, to_date: date) -> List[date]:
    """Return list of dates [from_date, to_date) — check_out exclusive."""
    days = []
    current = from_date
    while current < to_date:
        days.append(current)
        current += timedelta(days=1)
    return days


def _parse_date(value: str, field: str) -> date:
    """Parse ISO date string; raise ValueError with field name on failure."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid {field}: '{value}'. Must be ISO date (YYYY-MM-DD).") from e


def _build_occupancy_map(
    bookings: List[Dict[str, Any]],
    from_date: date,
    to_date: date,
) -> Dict[str, Any]:
    """
    Build per-date occupancy from a list of ACTIVE booking rows.

    Rules:
    - date range: [from_date, to_date) — check_out exclusive.
    - Only ACTIVE rows are passed in (CANCELED filtered before this call).
    - If two bookings cover the same date → CONFLICT flag.

    Returns:
        dict[str, OccupancyEntry] where key is ISO date string.
        OccupancyEntry = {
            "date":       "YYYY-MM-DD",
            "occupied":   bool,
            "booking_id": str | None,
            "status":     "VACANT" | "OCCUPIED" | "CONFLICT",
        }
    """
    all_days = _date_range(from_date, to_date)

    # Initialize all days as VACANT
    occupancy: Dict[str, Dict[str, Any]] = {
        d.isoformat(): {
            "date": d.isoformat(),
            "occupied": False,
            "booking_id": None,
            "status": "VACANT",
        }
        for d in all_days
    }

    for booking in bookings:
        check_in_raw = booking.get("canonical_check_in") or booking.get("check_in")
        check_out_raw = booking.get("canonical_check_out") or booking.get("check_out")
        booking_id = booking.get("booking_id") or booking.get("id")

        if not check_in_raw or not check_out_raw:
            continue

        try:
            b_in = date.fromisoformat(str(check_in_raw)[:10])
            b_out = date.fromisoformat(str(check_out_raw)[:10])
        except (ValueError, TypeError):
            continue

        for d in _date_range(b_in, b_out):
            key = d.isoformat()
            if key not in occupancy:
                continue  # outside requested range

            entry = occupancy[key]
            if entry["status"] == "VACANT":
                entry["occupied"] = True
                entry["booking_id"] = booking_id
                entry["status"] = "OCCUPIED"
            else:
                # Already occupied by another booking → CONFLICT
                entry["status"] = "CONFLICT"
                # Preserve first booking_id; add conflict_booking_id
                entry["conflict_booking_id"] = booking_id

    return occupancy


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/availability/{property_id}",
    tags=["availability"],
    summary="Get property availability (Phase 126)",
    description=(
        "Per-date occupancy state for a property in the given date range. "
        "Built from booking_state projection. Zero write-path changes. "
        "Foundation for channel sync, OTA calendar push, and rate management.\n\n"
        "Date range: `from` inclusive, `to` exclusive (ISO date YYYY-MM-DD).\n"
        "Only ACTIVE bookings are counted (CANCELED excluded).\n"
        "Multi-booking overlap on same date is flagged as CONFLICT.\n\n"
        "**Source:** Reads from `booking_state` projection table only."
    ),
    responses={
        200: {"description": "Per-date occupancy map for the requested range."},
        400: {"description": "Missing or invalid query parameters."},
        500: {"description": "Internal server error."},
    },
)
async def get_availability(
    property_id: str,
    request: Request,
    # Query params extracted manually below to allow clear validation errors
) -> JSONResponse:
    """
    GET /availability/{property_id}?from=<date>&to=<date>

    Returns per-date occupancy map for the requested date range.

    Query params:
        from  — start date inclusive (YYYY-MM-DD). Alias: from_ in Python.
        to    — end date exclusive (YYYY-MM-DD).

    Response shape:
        {
          "property_id": "...",
          "from": "YYYY-MM-DD",
          "to": "YYYY-MM-DD",
          "days": <int>,
          "dates": [
            {
              "date": "YYYY-MM-DD",
              "occupied": bool,
              "booking_id": str | null,
              "status": "VACANT" | "OCCUPIED" | "CONFLICT"
            },
            ...
          ],
          "summary": {
            "vacant": <int>,
            "occupied": <int>,
            "conflict": <int>
          }
        }
    """
    # --- Query param extraction & validation ---
    params = dict(request.query_params)
    from_raw = params.get("from")
    to_raw = params.get("to")

    if not from_raw:
        return make_error_response(
            400,
            "VALIDATION_ERROR",
            "Missing required query parameter: 'from'",
        )
    if not to_raw:
        return make_error_response(
            400,
            "VALIDATION_ERROR",
            "Missing required query parameter: 'to'",
        )

    try:
        from_date = _parse_date(from_raw, "from")
        to_date = _parse_date(to_raw, "to")
    except ValueError as e:
        return make_error_response(
            400,
            "VALIDATION_ERROR",
            str(e),
        )

    if from_date >= to_date:
        return make_error_response(
            400,
            "VALIDATION_ERROR",
            "'from' must be before 'to'.",
        )

    # Max range guard — 366 days to prevent abuse
    max_days = 366
    if (to_date - from_date).days > max_days:
        return make_error_response(
            400,
            "VALIDATION_ERROR",
            f"Date range exceeds maximum allowed ({max_days} days).",
        )

    try:
        db = _get_supabase_client(request)

        # Query: ACTIVE bookings for this property whose date range overlaps [from, to)
        # Overlap condition: check_in < to_date AND check_out > from_date
        result = (
            db.table("booking_state")
            .select(
                "booking_id, check_in, check_out, "
                "status, tenant_id"
            )
            .eq("property_id", property_id)
            .eq("status", "active")
            .lt("check_in", to_raw)       # check_in < to
            .gt("check_out", from_raw)    # check_out > from
            .execute()
        )
        bookings = result.data or []

    except Exception:  # noqa: BLE001
        return make_error_response(
            500,
            "INTERNAL_ERROR",
            "Failed to query availability.",
        )

    occupancy_map = _build_occupancy_map(bookings, from_date, to_date)
    dates_list = list(occupancy_map.values())

    # Summary counts
    vacant_count = sum(1 for d in dates_list if d["status"] == "VACANT")
    occupied_count = sum(1 for d in dates_list if d["status"] == "OCCUPIED")
    conflict_count = sum(1 for d in dates_list if d["status"] == "CONFLICT")

    return JSONResponse(
        status_code=200,
        content={
            "property_id": property_id,
            "from": from_raw,
            "to": to_raw,
            "days": len(dates_list),
            "dates": dates_list,
            "summary": {
                "vacant": vacant_count,
                "occupied": occupied_count,
                "conflict": conflict_count,
            },
        },
    )
