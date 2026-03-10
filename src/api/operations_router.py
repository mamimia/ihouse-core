"""
Phase 153 — Operations Today Endpoint

Provides a single in-memory aggregation of booking_state for the 7AM
Operations Dashboard view. No writes. JWT required. Tenant-scoped.

Endpoint:
  GET /operations/today
    Returns: arrivals_today, departures_today, cleanings_due_today
    All counts are for the authenticated tenant and current calendar date (UTC).

Design:
  - Reads booking_state rows where status = 'active' and check_in or check_out
    matches today's date.
  - Computation is purely in-memory — no separate projections table needed.
  - cleanings_due_today = departures_today (every departure triggers a cleaning).
  - Empty booking_state → all counts return 0 (never errors).
  - Date parameter `as_of` (optional, YYYY-MM-DD) allows override for testing.

Invariant: Read-only. Never writes to any table.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
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
# Aggregation helper
# ---------------------------------------------------------------------------

def _compute_today(
    db: Any,
    tenant_id: str,
    as_of: Optional[str] = None,
) -> dict:
    """
    Aggregate booking_state for today's date:
      - arrivals_today:   active bookings with check_in == today
      - departures_today: active bookings with check_out == today
      - cleanings_due_today: same as departures_today

    Returns dict with counts. Never raises — returns zeros on error.
    The `as_of` param overrides today's date (ISO YYYY-MM-DD, for testing).
    """
    try:
        today_str = as_of if as_of else date.today().isoformat()

        # Fetch all active bookings for this tenant in one query
        result = (
            db.table("booking_state")
            .select("booking_id, check_in, check_out, status")
            .eq("tenant_id", tenant_id)
            .eq("status", "active")
            .execute()
        )
        rows = result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "_compute_today: DB error for tenant=%s: %s", tenant_id, exc
        )
        return {
            "date":               today_str if as_of else date.today().isoformat(),
            "arrivals_today":     0,
            "departures_today":   0,
            "cleanings_due_today": 0,
        }

    arrivals   = sum(1 for r in rows if str(r.get("check_in")  or "") == today_str)
    departures = sum(1 for r in rows if str(r.get("check_out") or "") == today_str)

    return {
        "date":               today_str,
        "arrivals_today":     arrivals,
        "departures_today":   departures,
        "cleanings_due_today": departures,   # 1:1 with departures
    }


# ---------------------------------------------------------------------------
# GET /operations/today
# ---------------------------------------------------------------------------

@router.get(
    "/operations/today",
    tags=["operations"],
    summary="Today's operational summary (arrivals, departures, cleanings)",
    responses={
        200: {"description": "Today's operational counts for this tenant"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_operations_today(
    as_of:     Optional[str] = Query(None, description="Override date (YYYY-MM-DD). Defaults to today UTC."),
    tenant_id: str           = Depends(jwt_auth),
    client:    Optional[Any] = None,
) -> JSONResponse:
    """
    Today's operational summary for the authenticated tenant.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only this tenant's bookings are counted.

    **Response fields:**
    - `date`               — the date used for the counts (ISO YYYY-MM-DD)
    - `arrivals_today`     — active bookings with check_in == today
    - `departures_today`   — active bookings with check_out == today
    - `cleanings_due_today` — same as departures_today (1:1 with departures)
    - `generated_at`       — ISO UTC timestamp of this response

    **Source:** `booking_state` — read-only.
    """
    try:
        db     = client if client is not None else _get_supabase_client()
        counts = _compute_today(db, tenant_id, as_of)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":    tenant_id,
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                **counts,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /operations/today error for tenant=%s: %s", tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
