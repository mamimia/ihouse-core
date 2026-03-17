"""
Phase 71 — Booking State Query API
Phase 106 — Booking List Query API
Phase 109 — Booking Date Range Search
Phase 129 — Booking Search: source filter, check_out range, sort_by/sort_dir
Phase 158 — Amendment History sub-endpoint
Phase 160 — Booking Flags: PATCH /{id}/flags + GET enriched with flags

GET /bookings/{booking_id}    — single booking state (Phase 71), with flags (Phase 160)
GET /bookings                 — list bookings by tenant, with filters (106/109/129)
GET /bookings/{booking_id}/amendments — amendment history (Phase 158)
PATCH /bookings/{booking_id}/flags    — set operator flags (Phase 160)

Filters (Phase 106): property_id, status, limit
Filters (Phase 109 addition): check_in_from, check_in_to (ISO 8601 YYYY-MM-DD)
Filters (Phase 129 addition): source (OTA provider), check_out_from, check_out_to,
                               sort_by (check_in|check_out|updated_at|created_at),
                               sort_dir (asc|desc)

Rules:
- JWT auth required on both endpoints.
- Tenant isolation enforced at DB level (.eq("tenant_id", tenant_id)).
- Reads from booking_state only. Never reads event_log directly.
- booking_state is a projection — its values are authoritative for read purposes,
  but the canonical source of truth remains the event_log.

Invariant (locked Phase 62+):
  These endpoints must NEVER write to booking_state or event_log.
  Strictly read-only projection endpoints.
"""
from __future__ import annotations

import logging
import os
import re as _re
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.envelope import ok, err
from services.audit_writer import write_audit_event

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
# GET /bookings/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/bookings/{booking_id}",
    tags=["bookings"],
    summary="Get current booking state",
    responses={
        200: {"description": "Current booking state (from booking_state projection)"},
        401: {"description": "Missing or invalid JWT token"},
        404: {"description": "Booking not found for this tenant"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_booking(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return the current state of a booking from the `booking_state` projection.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** Only bookings belonging to the requesting tenant are
    returned. Cross-tenant reads return 404, not 403, to avoid leaking booking
    existence information.

    **Source:** Reads from `booking_state` projection table only.
    This is the operational read model — never the canonical source of truth.
    The event_log is the canonical authority.

    **Booking status values:**
    - `active` — booking is live
    - `canceled` — booking was canceled
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("booking_state")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )

        if not result.data:
            return err(
                "BOOKING_NOT_FOUND",
                "Booking not found for this tenant",
                status=404,
                booking_id=booking_id,
            )

        row = result.data[0]

        # Phase 160: enrich with operator flags (best-effort — None if no flags row)
        flags = None
        try:
            flags_result = (
                db.table("booking_flags")
                .select("*")
                .eq("booking_id", booking_id)
                .eq("tenant_id", tenant_id)
                .limit(1)
                .execute()
            )
            if flags_result.data:
                fr = flags_result.data[0]
                flags = {
                    "is_vip":       fr.get("is_vip"),
                    "is_disputed":  fr.get("is_disputed"),
                    "needs_review": fr.get("needs_review"),
                    "operator_note": fr.get("operator_note"),
                    "flagged_by":   fr.get("flagged_by"),
                    "updated_at":   fr.get("updated_at"),
                }
        except Exception:
            pass  # best-effort — never block the booking response

        return ok({
            "booking_id": row["booking_id"],
            "tenant_id": row["tenant_id"],
            "source": row.get("source"),
            "reservation_ref": row.get("reservation_ref"),
            "property_id": row.get("property_id"),
            "status": row.get("status"),
            "check_in": row.get("check_in"),
            "check_out": row.get("check_out"),
            "guest_name": row.get("guest_name"),
            "version": row.get("version"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "flags": flags,
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /bookings/%s error: %s", booking_id, exc)
        return err("INTERNAL_ERROR", "An unexpected internal error occurred", status=500)


# ---------------------------------------------------------------------------
# GET /bookings (Phase 106)
# ---------------------------------------------------------------------------

_VALID_STATUSES = frozenset({"active", "canceled", "observed", "blocked"})
_VALID_SORT_BY = frozenset({"check_in", "check_out", "updated_at", "created_at"})
# Map user-facing sort_by names to actual DB column names
_SORT_BY_COLUMN = {
    "check_in": "check_in",
    "check_out": "check_out",
    "updated_at": "updated_at_ms",
    "created_at": "updated_at_ms",  # no created_at column — fallback to updated_at_ms
}
_VALID_SORT_DIR = frozenset({"asc", "desc"})
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50
_DATE_RE = _re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


@router.get(
    "/bookings",
    tags=["bookings"],
    summary="List / search bookings for a tenant",
    responses={
        200: {"description": "Paginated list of bookings from booking_state projection"},
        400: {"description": "Invalid query parameter (e.g. unknown status or sort_by value)"},
        401: {"description": "Missing or invalid JWT token"},
        500: {"description": "Unexpected internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_bookings(
    property_id: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    q: Optional[str] = None,  # Phase 371: free-text search
    check_in_from: Optional[str] = None,
    check_in_to: Optional[str] = None,
    check_out_from: Optional[str] = None,
    check_out_to: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "desc",
    limit: int = _DEFAULT_LIMIT,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return a paginated list of bookings from the `booking_state` projection.

    **Authentication:** Bearer JWT required. `sub` claim used as `tenant_id`.

    **Tenant isolation:** All results are scoped to the authenticated tenant.

    **Query parameters:**
    - `property_id` — filter by property (optional)
    - `status` — filter by booking status: `active` or `canceled` (optional)
    - `source` — filter by OTA provider name e.g. `bookingcom`, `airbnb` (optional)
    - `check_in_from` — filter bookings with `check_in` ≥ this date (YYYY-MM-DD, optional)
    - `check_in_to` — filter bookings with `check_in` ≤ this date (YYYY-MM-DD, optional)
    - `check_out_from` — filter bookings with `check_out` ≥ this date (YYYY-MM-DD, optional)
    - `check_out_to` — filter bookings with `check_out` ≤ this date (YYYY-MM-DD, optional)
    - `sort_by` — field to sort by: `check_in`, `check_out`, `updated_at` (default), `created_at`
    - `sort_dir` — `asc` or `desc` (default `desc`)
    - `limit` — max results to return (1–100, default 50)

    **Source:** Reads from `booking_state` projection table only.
    Never reads `event_log` directly.

    **Invariant:** Read-only. Never writes to any table.
    """
    # Validate status
    if status is not None and status not in _VALID_STATUSES:
        return err(
            "VALIDATION_ERROR",
            f"status must be one of: {sorted(_VALID_STATUSES)}",
            status=400,
        )

    # Validate sort_by
    if sort_by is not None and sort_by not in _VALID_SORT_BY:
        return err(
            "VALIDATION_ERROR",
            f"sort_by must be one of: {sorted(_VALID_SORT_BY)}",
            status=400,
        )

    # Validate sort_dir
    if sort_dir not in _VALID_SORT_DIR:
        return err(
            "VALIDATION_ERROR",
            f"sort_dir must be one of: {sorted(_VALID_SORT_DIR)}",
            status=400,
        )

    # Validate date range params
    for field_name, field_val in [
        ("check_in_from", check_in_from),
        ("check_in_to", check_in_to),
        ("check_out_from", check_out_from),
        ("check_out_to", check_out_to),
    ]:
        if field_val is not None and not _DATE_RE.match(field_val):
            return err(
                "VALIDATION_ERROR",
                f"{field_name} must be a valid date in YYYY-MM-DD format",
                status=400,
            )

    # Clamp limit
    limit = max(1, min(limit, _MAX_LIMIT))
    _sort_field = _SORT_BY_COLUMN.get(sort_by or "updated_at", "updated_at_ms")
    _sort_desc = sort_dir == "desc"

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("booking_state")
            .select("*")
            .eq("tenant_id", tenant_id)
        )

        if property_id is not None:
            query = query.eq("property_id", property_id)

        if status is not None:
            query = query.eq("status", status)

        if source is not None:
            query = query.eq("source", source)

        # Phase 371: Free-text search across booking_id, reservation_ref, guest_name
        if q is not None and q.strip():
            search_term = q.strip()
            query = query.or_(
                f"booking_id.ilike.%{search_term}%,"
                f"reservation_ref.ilike.%{search_term}%,"
                f"guest_name.ilike.%{search_term}%"
            )

        if check_in_from is not None:
            query = query.gte("check_in", check_in_from)

        if check_in_to is not None:
            query = query.lte("check_in", check_in_to)

        if check_out_from is not None:
            query = query.gte("check_out", check_out_from)

        if check_out_to is not None:
            query = query.lte("check_out", check_out_to)

        result = query.limit(limit).order(_sort_field, desc=_sort_desc).execute()
        rows = result.data or []

        bookings = [
            {
                "booking_id":      r["booking_id"],
                "tenant_id":       r["tenant_id"],
                "source":          r.get("source"),
                "reservation_ref": r.get("reservation_ref"),
                "property_id":     r.get("property_id"),
                "status":          r.get("status"),
                "check_in":        r.get("check_in"),
                "check_out":       r.get("check_out"),
                "guest_name":      r.get("guest_name"),
                "version":         r.get("version"),
                "created_at":      r.get("created_at"),
                "updated_at":      r.get("updated_at_ms"),
            }
            for r in rows
        ]

        return ok({
            "tenant_id": tenant_id,
            "count":     len(bookings),
            "limit":     limit,
            "sort_by":   sort_by or "updated_at",
            "sort_dir":  sort_dir,
            "bookings":  bookings,
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /bookings error for tenant=%s: %s", tenant_id, exc)
        return err("INTERNAL_ERROR", "An unexpected internal error occurred", status=500)


# ---------------------------------------------------------------------------
# GET /bookings/{booking_id}/amendments  (Phase 158)
# ---------------------------------------------------------------------------

@router.get(
    "/bookings/{booking_id}/amendments",
    tags=["bookings"],
    summary="List amendment history for a booking (Phase 158)",
    description=(
        "Returns all `BOOKING_AMENDED` events from the `event_log` for a specific booking.\\n\\n"
        "Events are sorted by `received_at` ascending (oldest first).\\n\\n"
        "**Source:** `event_log` table — tenant-scoped. Read-only.\\n\\n"
        "**404** if the booking does not exist for this tenant.\\n\\n"
        "Empty list returned when the booking exists but has no amendments."
    ),
    responses={
        200: {"description": "List of BOOKING_AMENDED events."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Booking not found for this tenant."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_booking_amendments(
    booking_id: str,
    limit: int = 50,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /bookings/{booking_id}/amendments — BOOKING_AMENDED event history."""
    limit = max(1, min(limit, 100))
    try:
        db = client if client is not None else _get_supabase_client()

        # Verify booking exists for this tenant
        bk = (
            db.table("booking_state")
            .select("booking_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not (bk.data or []):
            return err(
                "BOOKING_NOT_FOUND",
                "Booking not found for this tenant",
                status=404,
                booking_id=booking_id,
            )

        # Fetch BOOKING_AMENDED events from event_log
        ev = (
            db.table("event_log")
            .select("*")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .eq("event_type", "BOOKING_AMENDED")
            .order("received_at", desc=False)
            .limit(limit)
            .execute()
        )
        rows = ev.data or []

        amendments = [
            {
                "envelope_id": r.get("envelope_id"),
                "booking_id":  r.get("booking_id"),
                "tenant_id":   r.get("tenant_id"),
                "event_type":  r.get("event_type"),
                "version":     r.get("version"),
                "received_at": r.get("received_at"),
                "payload":     r.get("payload"),
            }
            for r in rows
        ]

        return ok({
            "booking_id": booking_id,
            "tenant_id":  tenant_id,
            "count":      len(amendments),
            "amendments": amendments,
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /bookings/%s/amendments error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return err("INTERNAL_ERROR", "An unexpected internal error occurred", status=500)


# ---------------------------------------------------------------------------
# PATCH /bookings/{booking_id}/flags  (Phase 160)
# ---------------------------------------------------------------------------

_FLAG_BOOLEANS = frozenset({"is_vip", "is_disputed", "needs_review"})
_FLAG_STRINGS  = frozenset({"operator_note", "flagged_by"})
_ALL_FLAG_KEYS = _FLAG_BOOLEANS | _FLAG_STRINGS


@router.patch(
    "/bookings/{booking_id}/flags",
    tags=["bookings"],
    summary="Set operator flags on a booking (Phase 160)",
    description=(
        "Upserts the operator annotation row in `booking_flags` for a booking.\n\n"
        "**Body fields (all optional):**\n"
        "- `is_vip` (bool)\n"
        "- `is_disputed` (bool)\n"
        "- `needs_review` (bool)\n"
        "- `operator_note` (string)\n"
        "- `flagged_by` (string — username / operator ID)\n\n"
        "**400** if no recognised flag fields are present.\n"
        "**404** if the booking does not exist for this tenant.\n"
        "**Idempotent:** repeated calls with same values are safe (upsert on_conflict)."
    ),
    responses={
        200: {"description": "Flags upserted successfully."},
        400: {"description": "No valid flag fields in request body."},
        401: {"description": "Missing or invalid JWT."},
        404: {"description": "Booking not found for this tenant."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def patch_booking_flags(
    booking_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    PATCH /bookings/{booking_id}/flags

    Upsert operator annotations on `booking_flags` table.
    Tenant-isolated. Booking must exist for this tenant.
    """
    from datetime import datetime, timezone

    # --- validate body has at least one recognised key ---
    if not isinstance(body, dict):
        return err(
            "VALIDATION_ERROR",
            "Request body must be a JSON object.",
            status=400,
        )

    recognised = {k: v for k, v in body.items() if k in _ALL_FLAG_KEYS}
    if not recognised:
        return err(
            "VALIDATION_ERROR",
            f"Body must contain at least one of: {sorted(_ALL_FLAG_KEYS)}",
            status=400,
        )

    # --- type checks for boolean flags ---
    for key in _FLAG_BOOLEANS:
        if key in body and not isinstance(body[key], bool):
            return err(
                "VALIDATION_ERROR",
                f"'{key}' must be a boolean.",
                status=400,
            )

    try:
        db = client if client is not None else _get_supabase_client()

        # Verify booking exists for this tenant
        bk = (
            db.table("booking_state")
            .select("booking_id")
            .eq("booking_id", booking_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not (bk.data or []):
            return err(
                "BOOKING_NOT_FOUND",
                "Booking not found for this tenant",
                status=404,
                booking_id=booking_id,
            )

        # Build upsert payload
        now = datetime.now(tz=timezone.utc).isoformat()
        upsert_data: dict = {
            "booking_id": booking_id,
            "tenant_id":  tenant_id,
            "updated_at": now,
        }
        for key in _ALL_FLAG_KEYS:
            if key in body:
                upsert_data[key] = body[key]

        result = (
            db.table("booking_flags")
            .upsert(upsert_data, on_conflict="booking_id,tenant_id")
            .execute()
        )

        saved = result.data[0] if (result.data or []) else upsert_data

        # Phase 189 — Audit event (best-effort, non-blocking)
        write_audit_event(
            tenant_id=tenant_id,
            actor_id=tenant_id,
            action="BOOKING_FLAGS_UPDATED",
            entity_type="booking",
            entity_id=booking_id,
            payload={k: v for k, v in recognised.items()},
            client=db,
        )

        return ok({
            "booking_id":   booking_id,
            "tenant_id":    tenant_id,
            "flags": {
                "is_vip":       saved.get("is_vip"),
                "is_disputed":  saved.get("is_disputed"),
                "needs_review": saved.get("needs_review"),
                "operator_note": saved.get("operator_note"),
                "flagged_by":   saved.get("flagged_by"),
                "updated_at":   saved.get("updated_at", now),
            },
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "PATCH /bookings/%s/flags error for tenant=%s: %s",
            booking_id, tenant_id, exc,
        )
        return err("INTERNAL_ERROR", "An unexpected internal error occurred", status=500)

