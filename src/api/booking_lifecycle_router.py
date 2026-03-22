"""
Phase 242 — Booking Lifecycle State Machine Visualization API

GET /admin/bookings/lifecycle-states

A cross-provider view of how bookings are distributed across the booking
lifecycle state machine (active, canceled, amended), and how many transitions
(BOOKING_CREATED → BOOKING_AMENDED → BOOKING_CANCELED) have occurred.

This endpoint reads from two sources:
  - booking_state: current status per booking (active / canceled)
  - event_log: event_type counts to derive transition volumes

State machine visualized:
    [CREATED] → active
    [AMENDED] → still active (update)
    [CANCELED] → canceled (terminal)

Response shape:
    {
        "tenant_id": "...",
        "generated_at": "...",
        "total_bookings": 120,
        "state_distribution": {
            "active": 88,
            "canceled": 32
        },
        "by_provider": [
            {
                "provider": "airbnb",
                "total": 40,
                "active": 30,
                "canceled": 10,
                "active_pct": 75.0,
                "canceled_pct": 25.0
            }
        ],
        "transition_counts": {
            "BOOKING_CREATED": 120,
            "BOOKING_AMENDED": 45,
            "BOOKING_CANCELED": 32
        },
        "amendment_rate_pct": 37.5,
        "cancellation_rate_pct": 26.7
    }

Architecture invariants:
    - Reads booking_state and event_log ONLY.
    - Never writes. Never bypasses apply_envelope.
    - Tenant isolation via .eq("tenant_id", tenant_id).
    - JWT auth required.
    - Counts are at-a-point-in-time; no period filtering (all-time snapshot).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.capability_guard import require_capability
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical event types we track in the state machine
_TRACKED_EVENTS = frozenset(
    ["BOOKING_CREATED", "BOOKING_AMENDED", "BOOKING_CANCELED"]
)

#: Canonical booking_state statuses
_KNOWN_STATUSES = frozenset(["active", "canceled"])


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:  # pragma: no cover
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Data reads
# ---------------------------------------------------------------------------

def _read_booking_state(db: Any, tenant_id: str) -> List[dict]:
    """
    Read all booking_state rows for the tenant.
    Returns list of {booking_id, source, status} dicts.
    Never raises — returns [] on failure.
    """
    try:
        result = (
            db.table("booking_state")
            .select("booking_id, source, status")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return result.data or []
    except Exception:  # noqa: BLE001
        logger.exception("booking_lifecycle_router: failed to read booking_state")
        return []


def _read_event_log_counts(db: Any, tenant_id: str) -> Dict[str, int]:
    """
    Read event_log to count BOOKING_CREATED, BOOKING_AMENDED, BOOKING_CANCELED
    for this tenant.

    Uses .in_() to match all tracked event types in a single query.
    Never raises — returns empty counts on failure.
    """
    counts: Dict[str, int] = {e: 0 for e in _TRACKED_EVENTS}
    try:
        result = (
            db.table("event_log")
            .select("event_type")
            .eq("tenant_id", tenant_id)
            .in_("event_type", list(_TRACKED_EVENTS))
            .execute()
        )
        rows = result.data or []
        for row in rows:
            et = row.get("event_type") or ""
            if et in counts:
                counts[et] += 1
    except Exception:  # noqa: BLE001
        logger.exception("booking_lifecycle_router: failed to read event_log")
    return counts


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _state_distribution(bookings: List[dict]) -> Dict[str, int]:
    """Count bookings by status (active / canceled / unknown)."""
    dist: Dict[str, int] = {}
    for row in bookings:
        status = (row.get("status") or "unknown").lower()
        dist[status] = dist.get(status, 0) + 1
    return dist


def _by_provider(bookings: List[dict]) -> List[Dict[str, Any]]:
    """
    Group bookings by source provider.
    Returns list sorted by total bookings descending.
    Each entry: {provider, total, active, canceled, active_pct, canceled_pct}.
    """
    agg: Dict[str, Dict[str, int]] = {}
    for row in bookings:
        provider = row.get("source") or "unknown"
        if provider not in agg:
            agg[provider] = {"total": 0, "active": 0, "canceled": 0}
        agg[provider]["total"] += 1
        status = (row.get("status") or "unknown").lower()
        if status in agg[provider]:
            agg[provider][status] += 1

    result = []
    for provider, counts in agg.items():
        total = counts["total"]
        active = counts["active"]
        canceled = counts["canceled"]
        result.append(
            {
                "provider": provider,
                "total": total,
                "active": active,
                "canceled": canceled,
                "active_pct": round(active / total * 100, 1) if total > 0 else 0.0,
                "canceled_pct": round(canceled / total * 100, 1) if total > 0 else 0.0,
            }
        )

    result.sort(key=lambda x: (-x["total"], x["provider"]))
    return result


def _rate_pct(numerator: int, denominator: int) -> Optional[float]:
    """Return percentage rounded to 1dp, or null if denominator is 0."""
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 1)


# ---------------------------------------------------------------------------
# GET /admin/bookings/lifecycle-states
# ---------------------------------------------------------------------------

@router.get(
    "/admin/bookings/lifecycle-states",
    tags=["admin"],
    summary="Booking lifecycle state machine distribution and transition counts",
    responses={
        200: {"description": "Booking state machine snapshot with provider breakdown"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_lifecycle_states(
    tenant_id: str = Depends(jwt_auth),
    _cap: None = Depends(require_capability("bookings")),
    _client: Optional[Any] = None,
) -> JSONResponse:
    """
    Cross-provider booking lifecycle state machine snapshot for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **No query parameters required** — returns an all-time snapshot.

    **Returns:**
    - `state_distribution` — count of bookings per status (active / canceled)
    - `by_provider` — per-OTA breakdown with active/canceled counts and percentages
    - `transition_counts` — how many BOOKING_CREATED / BOOKING_AMENDED / BOOKING_CANCELED events
    - `amendment_rate_pct` — % of created bookings that were later amended
    - `cancellation_rate_pct` — % of created bookings that were later canceled

    **Sources:** Reads from `booking_state` (current status) and `event_log` (transition counts).
    """
    from datetime import datetime, timezone

    generated_at = datetime.now(tz=timezone.utc).isoformat()

    try:
        db = _client if _client is not None else _get_supabase_client()

        bookings = _read_booking_state(db, tenant_id)
        transition_counts = _read_event_log_counts(db, tenant_id)

        state_dist = _state_distribution(bookings)
        provider_breakdown = _by_provider(bookings)

        created_count = transition_counts.get("BOOKING_CREATED", 0)
        amended_count = transition_counts.get("BOOKING_AMENDED", 0)
        canceled_count = transition_counts.get("BOOKING_CANCELED", 0)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "generated_at": generated_at,
                "total_bookings": len(bookings),
                "state_distribution": state_dist,
                "by_provider": provider_breakdown,
                "transition_counts": transition_counts,
                "amendment_rate_pct": _rate_pct(amended_count, created_count),
                "cancellation_rate_pct": _rate_pct(canceled_count, created_count),
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/bookings/lifecycle-states error for tenant=%s: %s",
            tenant_id,
            exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
