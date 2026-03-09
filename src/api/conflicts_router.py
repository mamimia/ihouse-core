"""
Phase 128 — Conflict Center

Provides a tenant-scoped view of all active booking conflicts across all (or one)
properties. A conflict exists when two or more ACTIVE bookings share at least one
overlapping date for the same property.

This router:
- Reads from booking_state only (same source as availability_projection, Phase 126).
- Never reads event_log, booking_financial_facts, or tasks.
- Never writes to any table.
- JWT auth required (tenant-scoped via X-Tenant-ID header or jwt_auth Depends).
- Computes conflicts in Python (no DB-level date arithmetic).

Endpoint:
    GET /conflicts?property_id=<optional>

Response:
    {
        "tenant_id": "...",
        "conflicts": [
            {
                "property_id": "prop_1",
                "booking_a": "bookingcom_R001",
                "booking_b": "airbnb_X002",
                "overlap_dates": ["2026-04-05", "2026-04-06"],
                "overlap_start": "2026-04-05",
                "overlap_end": "2026-04-07",   # exclusive
                "severity": "WARNING" | "CRITICAL"
            }
        ],
        "summary": {
            "total_conflicts": 1,
            "properties_affected": 1,
            "bookings_involved": 2
        }
    }

Severity:
    - CRITICAL: overlap >= 3 nights
    - WARNING:  overlap 1-2 nights

Design:
    - All ACTIVE bookings are fetched (or just a given property_id's bookings).
    - Group by property_id.
    - For each property, collect per-date occupancy per booking.
    - Any date occupied by 2+ bookings → conflict pair.
    - Pairs are deduplicated (A,B) vs (B,A).
    - Overlap_dates = sorted list of conflicting dates.
    - overlap_start/end derived from overlap_dates (min, max+1day).
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from itertools import combinations
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# DB client helper
# ---------------------------------------------------------------------------

def _get_supabase_client(request: Request) -> Any:
    """Resolve Supabase client from app.state (standard pattern)."""
    return request.app.state.supabase


# ---------------------------------------------------------------------------
# Conflict computation — pure Python
# ---------------------------------------------------------------------------

def _date_set_for_booking(check_in_str: str, check_out_str: str) -> Set[date]:
    """
    Return a set of dates [check_in, check_out) — check_out exclusive.
    Returns empty set on parse error.
    """
    try:
        ci = date.fromisoformat(check_in_str)
        co = date.fromisoformat(check_out_str)
    except (ValueError, TypeError):
        return set()
    dates: Set[date] = set()
    current = ci
    while current < co:
        dates.add(current)
        current += timedelta(days=1)
    return dates


def _find_conflicts_for_property(
    bookings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Given a list of ACTIVE bookings for a single property, find all pairs
    that overlap on at least one date.

    Returns a list of conflict dicts:
        {
            "booking_a": str,
            "booking_b": str,
            "overlap_dates": List[str],  # sorted ISO strings
            "overlap_start": str,
            "overlap_end": str,          # exclusive (day after last overlap)
            "severity": "CRITICAL" | "WARNING",
        }
    """
    # Build per-booking date sets
    booking_dates: List[Tuple[str, Set[date]]] = []
    for b in bookings:
        bid = b.get("booking_id", "")
        ci = b.get("canonical_check_in") or b.get("check_in", "")
        co = b.get("canonical_check_out") or b.get("check_out", "")
        ds = _date_set_for_booking(ci, co)
        if bid and ds:
            booking_dates.append((bid, ds))

    conflicts: List[Dict[str, Any]] = []
    seen_pairs: Set[Tuple[str, str]] = set()

    for (bid_a, dates_a), (bid_b, dates_b) in combinations(booking_dates, 2):
        pair = (min(bid_a, bid_b), max(bid_a, bid_b))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        overlap = dates_a & dates_b
        if not overlap:
            continue

        sorted_overlap = sorted(overlap)
        overlap_start = sorted_overlap[0].isoformat()
        overlap_end = (sorted_overlap[-1] + timedelta(days=1)).isoformat()
        nights = len(sorted_overlap)
        severity = "CRITICAL" if nights >= 3 else "WARNING"

        conflicts.append({
            "booking_a": min(bid_a, bid_b),
            "booking_b": max(bid_a, bid_b),
            "overlap_dates": [d.isoformat() for d in sorted_overlap],
            "overlap_start": overlap_start,
            "overlap_end": overlap_end,
            "severity": severity,
        })

    return conflicts


def _find_all_conflicts(
    bookings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group bookings by property_id and find conflicts in each group.
    Returns a flat list of conflict dicts (with property_id added).
    """
    # Group by property_id
    by_property: Dict[str, List[Dict[str, Any]]] = {}
    for b in bookings:
        pid = b.get("property_id", "")
        if pid:
            by_property.setdefault(pid, []).append(b)

    all_conflicts: List[Dict[str, Any]] = []
    for pid, prop_bookings in sorted(by_property.items()):
        for conflict in _find_conflicts_for_property(prop_bookings):
            all_conflicts.append({"property_id": pid, **conflict})

    return all_conflicts


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/conflicts",
    tags=["conflicts"],
    summary="Conflict Center — active booking overlaps (Phase 128)",
    description=(
        "Returns all active booking conflicts (overlapping dates on the same property) "
        "for the authenticated tenant.\n\n"
        "**Filter:** Optionally filter by `property_id`.\n\n"
        "**Conflict definition:** Two or more ACTIVE bookings share at least one date "
        "on the same property (check_in inclusive, check_out exclusive).\n\n"
        "**Severity:** CRITICAL ≥ 3 nights overlap; WARNING 1-2 nights.\n\n"
        "**Source:** `booking_state` — read-only. Never reads event_log, "
        "booking_financial_facts, or tasks."
    ),
    responses={
        200: {"description": "Active conflicts for this tenant."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_conflicts(
    request: Request,
    tenant_id: str = Depends(jwt_auth),
    property_id: Optional[str] = None,
) -> JSONResponse:
    """
    GET /conflicts?property_id=<optional>

    Returns all active booking overlaps (conflicts) for the authenticated tenant.

    Authentication: Bearer JWT required. tenant_id from sub claim.

    Query parameters:
        property_id (optional): if provided, only check this property.

    Reads from: booking_state (ACTIVE only). Never writes.
    """
    try:
        db = _get_supabase_client(request)

        # Fetch all ACTIVE bookings for this tenant (optionally scoped to property)
        query = (
            db.table("booking_state")
            .select(
                "booking_id, property_id, "
                "canonical_check_in, canonical_check_out, "
                "lifecycle_status, tenant_id"
            )
            .eq("tenant_id", tenant_id)
            .eq("lifecycle_status", "ACTIVE")
        )
        if property_id:
            query = query.eq("property_id", property_id)

        result = query.execute()
        bookings = result.data or []

    except Exception:  # noqa: BLE001
        return make_error_response(
            500,
            "INTERNAL_ERROR",
            "Failed to query booking state.",
        )

    conflicts = _find_all_conflicts(bookings)

    # Summary
    affected_properties = {c["property_id"] for c in conflicts}
    involved_bookings: Set[str] = set()
    for c in conflicts:
        involved_bookings.add(c["booking_a"])
        involved_bookings.add(c["booking_b"])

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "conflicts": conflicts,
            "summary": {
                "total_conflicts": len(conflicts),
                "properties_affected": len(affected_properties),
                "bookings_involved": len(involved_bookings),
            },
        },
    )
