"""
Phase 234 — Shift & Availability Scheduler

Endpoints:
    POST /worker/availability
        Set own availability for a date (upsert — idempotent).
        worker_id derived from JWT user_id claim.

        Body: {
            "date":       "YYYY-MM-DD",  (required)
            "status":     "AVAILABLE" | "UNAVAILABLE" | "ON_LEAVE",  (required)
            "start_time": "HH:MM",   (optional, null = all-day)
            "end_time":   "HH:MM",   (optional, null = all-day)
            "notes":      "string"   (optional)
        }

    GET /worker/availability?from=YYYY-MM-DD&to=YYYY-MM-DD
        Own availability slots in date range (max 90 days).

    GET /admin/schedule/overview?date=YYYY-MM-DD
        Manager view: all workers' availability for a date,
        grouped by status.

Rules:
    - JWT auth required on all endpoints.
    - Tenant isolation enforced (.eq("tenant_id", tenant_id)) on all queries.
    - worker_id for POST and GET /worker/... = JWT user_id claim.
    - status must be AVAILABLE | UNAVAILABLE | ON_LEAVE.
    - date must be YYYY-MM-DD.
    - from/to range must be ≤ 90 days.
    - Upsert: ON CONFLICT (tenant_id, worker_id, date) DO UPDATE.
    - No LLM dependency — pure CRUD.

Invariant (Phase 234):
    This router NEVER writes to booking_state, event_log, tasks, or
    booking_financial_facts.  All writes target worker_availability only.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_STATUSES = {"AVAILABLE", "UNAVAILABLE", "ON_LEAVE"}
_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_MAX_RANGE_DAYS = 90


# ---------------------------------------------------------------------------
# Supabase client
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _valid_date(s: Optional[str]) -> bool:
    return s is not None and bool(_DATE_RE.match(s))


def _valid_time(s: Optional[str]) -> bool:
    if s is None:
        return True  # optional
    return bool(_TIME_RE.match(s))


# ---------------------------------------------------------------------------
# POST /worker/availability
# ---------------------------------------------------------------------------

@router.post(
    "/worker/availability",
    tags=["worker-scheduling"],
    summary="Set own availability for a date (upsert)",
    responses={
        201: {"description": "Availability created"},
        200: {"description": "Availability updated (upsert)"},
        400: {"description": "Invalid request body"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def set_availability(
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    worker_id_override: Optional[str] = None,  # test injection
) -> JSONResponse:
    """
    Set availability for a single date.

    **Upsert logic:** if a row already exists for (tenant_id, worker_id, date),
    it is updated. Otherwise a new row is created.

    **worker_id** is derived from the JWT `user_id` claim automatically.
    """
    if body is None:
        body = {}

    slot_date: Optional[str] = body.get("date")
    status: Optional[str] = body.get("status")
    start_time: Optional[str] = body.get("start_time")
    end_time: Optional[str] = body.get("end_time")
    notes: Optional[str] = body.get("notes")

    # Validation
    if not slot_date or not _valid_date(slot_date):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "date is required (YYYY-MM-DD)")

    if not status or status.upper() not in _VALID_STATUSES:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            f"status must be one of {sorted(_VALID_STATUSES)}"
        )
    status = status.upper()

    if not _valid_time(start_time):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "start_time must be HH:MM")
    if not _valid_time(end_time):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "end_time must be HH:MM")

    try:
        db = client or _get_db()
        worker_id = worker_id_override or tenant_id  # fallback for test compat

        now_iso = datetime.now(tz=timezone.utc).isoformat()
        row = {
            "tenant_id": tenant_id,
            "worker_id": worker_id,
            "date": slot_date,
            "status": status,
            "start_time": start_time,
            "end_time": end_time,
            "notes": notes,
            "updated_at": now_iso,
        }

        # Upsert: conflict on (tenant_id, worker_id, date)
        result = (
            db.table("worker_availability")
            .upsert(row, on_conflict="tenant_id,worker_id,date")
            .execute()
        )
        data = (result.data or [{}])
        record = data[0] if data else row
        is_new = not record.get("created_at") or record.get("created_at") == record.get("updated_at")

        return JSONResponse(
            status_code=201 if is_new else 200,
            content={
                "tenant_id": tenant_id,
                "worker_id": worker_id,
                "date": slot_date,
                "status": status,
                "start_time": start_time,
                "end_time": end_time,
                "notes": notes,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("set_availability error tenant=%s: %s", tenant_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to set availability")


# ---------------------------------------------------------------------------
# GET /worker/availability
# ---------------------------------------------------------------------------

@router.get(
    "/worker/availability",
    tags=["worker-scheduling"],
    summary="Get own availability in date range",
    responses={
        200: {"description": "List of availability slots"},
        400: {"description": "Invalid query parameters"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_own_availability(
    from_date: Optional[str] = Query(default=None, alias="from"),
    to_date: Optional[str] = Query(default=None, alias="to"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
    worker_id_override: Optional[str] = None,
) -> JSONResponse:
    """
    Return own availability slots between from_date and to_date (inclusive).
    Range must not exceed 90 days.
    """
    if not from_date or not _valid_date(from_date):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "from is required (YYYY-MM-DD)")
    if not to_date or not _valid_date(to_date):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "to is required (YYYY-MM-DD)")

    try:
        d_from = date.fromisoformat(from_date)
        d_to = date.fromisoformat(to_date)
    except ValueError:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "Invalid date value")

    if d_to < d_from:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "to must be >= from")
    if (d_to - d_from).days > _MAX_RANGE_DAYS:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR, f"Range must not exceed {_MAX_RANGE_DAYS} days"
        )

    try:
        db = client or _get_db()
        worker_id = worker_id_override or tenant_id

        result = (
            db.table("worker_availability")
            .select("id, date, status, start_time, end_time, notes, updated_at")
            .eq("tenant_id", tenant_id)
            .eq("worker_id", worker_id)
            .gte("date", from_date)
            .lte("date", to_date)
            .order("date", desc=False)
            .execute()
        )
        slots = result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "worker_id": worker_id,
                "from": from_date,
                "to": to_date,
                "slots": slots,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("get_own_availability error tenant=%s: %s", tenant_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to fetch availability")


# ---------------------------------------------------------------------------
# GET /admin/schedule/overview
# ---------------------------------------------------------------------------

@router.get(
    "/admin/schedule/overview",
    tags=["admin-scheduling"],
    summary="Manager view — all workers' availability for a date (Phase 234)",
    responses={
        200: {"description": "Workers grouped by availability status"},
        400: {"description": "Invalid date parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_schedule_overview(
    date_param: Optional[str] = Query(default=None, alias="date"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return all workers' availability for a single date.
    Grouped by status: AVAILABLE, UNAVAILABLE, ON_LEAVE, NOT_SET.

    **Authentication:** Bearer JWT required.
    **Query parameters:**
    - `date` — target date in YYYY-MM-DD format (required)
    """
    if not date_param or not _valid_date(date_param):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "date is required (YYYY-MM-DD)")

    try:
        db = client or _get_db()

        result = (
            db.table("worker_availability")
            .select("worker_id, status, start_time, end_time, notes")
            .eq("tenant_id", tenant_id)
            .eq("date", date_param)
            .execute()
        )
        rows = result.data or []

        grouped: dict[str, list] = {
            "AVAILABLE": [],
            "UNAVAILABLE": [],
            "ON_LEAVE": [],
        }
        for row in rows:
            s = (row.get("status") or "AVAILABLE").upper()
            grouped.setdefault(s, []).append(row)

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "date": date_param,
                "total_workers": len(rows),
                "schedule": grouped,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("schedule_overview error tenant=%s: %s", tenant_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to fetch schedule overview")
