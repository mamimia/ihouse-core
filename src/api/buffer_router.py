"""
Phase 133 — OTA Ordering Buffer Inspector

GET /admin/buffer           — list buffer entries with optional filters
GET /admin/buffer/{id}      — single buffer entry by ID

The `ota_ordering_buffer` stores events that arrived before their
corresponding BOOKING_CREATED was processed. The buffer is the mechanism
that handles out-of-order event delivery: an amendment or cancellation
arriving before the booking exists is held here and replayed once the
booking is created.

This endpoint gives operators visibility into:
  - Events stuck in 'waiting' (ordering-blocked, not yet replayed)
  - Events that have been successfully replayed
  - How long an entry has been waiting (age)
  - Which booking_id and event_type are involved
  - Whether there's a corresponding DLQ entry (dlq_row_id)

Query parameters for GET /admin/buffer:
    - status (optional): "waiting" | "replayed" | "all" (default: "all")
    - booking_id (optional): filter by booking_id
    - limit (int, 1–100, default 50)

Response shape (list):
    {
        "total": int,
        "status_filter": str,
        "booking_id_filter": str | null,
        "entries": [
            {
                "id":          int,
                "booking_id":  str,
                "event_type":  str,
                "status":      "waiting" | "replayed",
                "dlq_row_id":  int | null,
                "created_at":  str | null,
                "age_seconds": int | null     # seconds since created_at
            }
        ]
    }

Response shape (single entry):
    { same fields as above, no extra fields }

Invariants:
    - Reads ota_ordering_buffer only. Global (not tenant-scoped).
    - Admin endpoint: JWT auth required (any valid tenant = operator access).
    - Never writes to any table.
    - age_seconds: computed from created_at vs. now (only for 'waiting' entries).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50
_VALID_STATUSES = frozenset({"waiting", "replayed", "all"})


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Age computation
# ---------------------------------------------------------------------------

def _age_seconds(created_at_str: Optional[str]) -> Optional[int]:
    """
    Compute how many seconds ago `created_at_str` was, relative to now (UTC).
    Returns None if created_at_str is missing or unparseable.
    Only meaningful for 'waiting' entries — caller decides whether to include.
    """
    if not created_at_str:
        return None
    try:
        # Handle both with and without trailing Z / offset
        ts = created_at_str.rstrip("Z")
        # Allow fractional seconds
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                created = datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
                delta = datetime.now(tz=timezone.utc) - created
                return max(0, int(delta.total_seconds()))
            except ValueError:
                continue
        return None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Row formatting
# ---------------------------------------------------------------------------

def _format_entry(row: Dict[str, Any]) -> Dict[str, Any]:
    """Format a raw ota_ordering_buffer row into the API response shape."""
    status = row.get("status") or "waiting"
    created_at = row.get("created_at")

    return {
        "id":          row.get("id"),
        "booking_id":  row.get("booking_id"),
        "event_type":  row.get("event_type"),
        "status":      status,
        "dlq_row_id":  row.get("dlq_row_id"),
        "created_at":  created_at,
        "age_seconds": _age_seconds(created_at),
    }


# ---------------------------------------------------------------------------
# GET /admin/buffer
# ---------------------------------------------------------------------------

@router.get(
    "/admin/buffer",
    tags=["admin"],
    summary="Buffer Inspector — list ordering buffer entries (Phase 133)",
    description=(
        "List entries in the OTA ordering buffer (`ota_ordering_buffer` table).\\n\\n"
        "The buffer holds events that arrived before their `BOOKING_CREATED` was "
        "processed (out-of-order delivery). 'waiting' entries are ordering-blocked "
        "and will be replayed once the booking exists.\\n\\n"
        "**Filters:** `status` (waiting/replayed/all), `booking_id`.\\n\\n"
        "**age_seconds:** time since the entry was created (useful for identifying "
        "stuck entries that have been waiting a long time).\\n\\n"
        "**Source:** `ota_ordering_buffer` — global (not tenant-scoped). Read-only."
    ),
    responses={
        200: {"description": "Buffer entries matching the requested filters."},
        400: {"description": "Invalid query parameter."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_buffer_entries(
    status: str = "all",
    booking_id: Optional[str] = None,
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/buffer?status=&booking_id=&limit=

    Lists ordering buffer entries. JWT auth required (admin surface).
    Reads from ota_ordering_buffer only. Never writes.
    """
    # Validate status filter
    if status not in _VALID_STATUSES:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"status must be one of: {sorted(_VALID_STATUSES)}",
        )

    # Clamp limit
    if limit < 1 or limit > _MAX_LIMIT:
        return make_error_response(
            status_code=400,
            code="VALIDATION_ERROR",
            message=f"limit must be between 1 and {_MAX_LIMIT}.",
        )

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("ota_ordering_buffer")
            .select("id, booking_id, event_type, status, dlq_row_id, created_at")
            .order("created_at", desc=True)
        )

        if status != "all":
            query = query.eq("status", status)

        if booking_id is not None:
            query = query.eq("booking_id", booking_id)

        query = query.limit(limit)
        result = query.execute()
        rows: List[Dict[str, Any]] = result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/buffer error: %s", exc)
        return make_error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Failed to query ordering buffer.",
        )

    entries = [_format_entry(r) for r in rows]

    return JSONResponse(
        status_code=200,
        content={
            "total":              len(entries),
            "status_filter":      status,
            "booking_id_filter":  booking_id,
            "entries":            entries,
        },
    )


# ---------------------------------------------------------------------------
# GET /admin/buffer/{entry_id}
# ---------------------------------------------------------------------------

@router.get(
    "/admin/buffer/{entry_id}",
    tags=["admin"],
    summary="Buffer Inspector — single buffer entry by ID (Phase 133)",
    description=(
        "Retrieve a single ordering buffer entry by its integer `id`.\\n\\n"
        "Use this after finding an entry via `GET /admin/buffer` to inspect "
        "its full detail.\\n\\n"
        "**Source:** `ota_ordering_buffer` — global. Read-only."
    ),
    responses={
        200: {"description": "Full buffer entry detail."},
        400: {"description": "Invalid entry_id format (must be an integer)."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "No buffer entry found with this ID."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_buffer_entry(
    entry_id: int,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/buffer/{entry_id}

    Returns a single ordering buffer entry by integer ID. JWT auth required.
    Reads from ota_ordering_buffer only. Never writes.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("ota_ordering_buffer")
            .select("id, booking_id, event_type, status, dlq_row_id, created_at")
            .eq("id", entry_id)
            .limit(1)
            .execute()
        )
        rows: List[Dict[str, Any]] = result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/buffer/%s error: %s", entry_id, exc)
        return make_error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Failed to query ordering buffer.",
        )

    if not rows:
        return make_error_response(
            status_code=404,
            code="NOT_FOUND",
            message=f"No buffer entry found with id: {entry_id}",
        )

    return JSONResponse(
        status_code=200,
        content=_format_entry(rows[0]),
    )
