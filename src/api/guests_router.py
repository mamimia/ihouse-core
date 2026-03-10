"""
Phase 192 — Guest Profile Foundation

Standalone guest identity CRUD endpoints.

  POST   /guests                  Create a new guest record
  GET    /guests                  List guests for tenant (?search=, ?limit=)
  GET    /guests/{id}             Retrieve a single guest by UUID
  PATCH  /guests/{id}             Partial-update one or more fields

Rules:
  - JWT auth required on all endpoints. `sub` claim = tenant_id.
  - Tenant isolation: reads and writes are always filtered by tenant_id.
    Cross-tenant GETs return 404 (no 403 to avoid existence leaks).
  - GET /guests: max 200 rows. ?limit=N overrides up to 200.
  - PATCH: only fields present in the request body are updated.
    updated_at is always refreshed.
  - No DELETE endpoint — guests are decommissioned via notes.
  - This table is reference data. It has NO foreign-key relationship with
    event_log or booking_state. It is completely outside the canonical
    event spine.

Distinction from Phase 159 guest_profile:
  guest_profile = read-only PII extracted from OTA webhook at create time.
  guests        = first-class identity record managed by operators.
"""
from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_LIMIT = 200


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# POST /guests
# ---------------------------------------------------------------------------

@router.post(
    "/guests",
    tags=["guests"],
    summary="Create a new guest identity record",
    status_code=201,
    responses={
        201: {"description": "Guest created successfully"},
        400: {"description": "Missing required field (full_name)"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_guest(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Create a new guest record for the authenticated tenant.

    **Required:** `full_name`
    **Optional:** `email`, `phone`, `nationality`, `passport_no`, `notes`
    """
    full_name = (body.get("full_name") or "").strip()
    if not full_name:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "full_name is required and must be non-empty"},
        )

    row = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "full_name": full_name,
        "email": body.get("email") or None,
        "phone": body.get("phone") or None,
        "nationality": body.get("nationality") or None,
        "passport_no": body.get("passport_no") or None,
        "notes": body.get("notes") or None,
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("guests").insert(row).execute()
        created = (result.data or [{}])[0]
        return JSONResponse(status_code=201, content=_serialize(created))

    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /guests error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /guests
# ---------------------------------------------------------------------------

@router.get(
    "/guests",
    tags=["guests"],
    summary="List guest records for the tenant",
    responses={
        200: {"description": "List of guests"},
        400: {"description": "Invalid limit parameter"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_guests(
    search: Optional[str] = None,
    limit: Optional[int] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    List guests for the authenticated tenant.

    **Query parameters:**
    - `search` *(optional)* — case-insensitive substring match on `full_name` or `email`.
    - `limit` *(optional)* — max rows to return (1–200, default 200).
    """
    if limit is not None and (limit < 1 or limit > _MAX_LIMIT):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"limit must be between 1 and {_MAX_LIMIT}"},
        )
    effective_limit = limit if limit is not None else _MAX_LIMIT

    try:
        db = client if client is not None else _get_supabase_client()
        query = (
            db.table("guests")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("created_at", desc=True)
            .limit(effective_limit)
        )
        result = query.execute()
        rows = result.data or []

        # Optional in-memory search filter (DB ilike not available on all clients)
        if search:
            term = search.lower()
            rows = [
                r for r in rows
                if term in (r.get("full_name") or "").lower()
                or term in (r.get("email") or "").lower()
            ]

        return JSONResponse(
            status_code=200,
            content={"count": len(rows), "guests": [_serialize(r) for r in rows]},
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /guests error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /guests/{id}
# ---------------------------------------------------------------------------

@router.get(
    "/guests/{guest_id}",
    tags=["guests"],
    summary="Retrieve a single guest by UUID",
    responses={
        200: {"description": "Guest record"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Guest not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_guest(
    guest_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Retrieve a guest by UUID.

    Returns 404 for both unknown IDs and cross-tenant requests
    (no 403 to avoid existence leaks).
    """
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("guests")
            .select("*")
            .eq("id", guest_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"id": guest_id, "detail": "Guest not found"},
            )
        return JSONResponse(status_code=200, content=_serialize(rows[0]))

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /guests/%s error for tenant=%s: %s", guest_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PATCH /guests/{id}
# ---------------------------------------------------------------------------

_PATCHABLE_FIELDS = frozenset({"full_name", "email", "phone", "nationality", "passport_no", "notes"})


@router.patch(
    "/guests/{guest_id}",
    tags=["guests"],
    summary="Partially update a guest record",
    responses={
        200: {"description": "Updated guest record"},
        400: {"description": "Validation error (empty full_name or empty patch body)"},
        401: {"description": "Missing or invalid JWT"},
        404: {"description": "Guest not found"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def patch_guest(
    guest_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Partially update a guest record.

    Only fields present in the request body are updated.
    `updated_at` is always refreshed.

    **Patchable fields:** `full_name`, `email`, `phone`, `nationality`, `passport_no`, `notes`
    """
    # Build the update payload from only recognised, present fields
    updates: dict = {}
    for field in _PATCHABLE_FIELDS:
        if field in body:
            updates[field] = body[field] or None  # empty string → None (except full_name)

    # full_name must not be blanked
    if "full_name" in updates:
        fn = (updates["full_name"] or "").strip()
        if not fn:
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "full_name must not be empty"},
            )
        updates["full_name"] = fn

    if not updates:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Patch body must contain at least one patchable field"},
        )

    # Always refresh updated_at
    updates["updated_at"] = "now()"

    try:
        db = client if client is not None else _get_supabase_client()

        # Confirm guest exists for this tenant before patching
        check = (
            db.table("guests")
            .select("id")
            .eq("id", guest_id)
            .eq("tenant_id", tenant_id)
            .limit(1)
            .execute()
        )
        if not (check.data or []):
            return make_error_response(
                status_code=404,
                code=ErrorCode.NOT_FOUND,
                extra={"id": guest_id, "detail": "Guest not found"},
            )

        result = (
            db.table("guests")
            .update(updates)
            .eq("id", guest_id)
            .eq("tenant_id", tenant_id)
            .execute()
        )
        updated = (result.data or [{}])[0]
        return JSONResponse(status_code=200, content=_serialize(updated))

    except Exception as exc:  # noqa: BLE001
        logger.exception("PATCH /guests/%s error for tenant=%s: %s", guest_id, tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Internal serialiser
# ---------------------------------------------------------------------------

def _serialize(row: dict) -> dict:
    """Return a clean JSON-safe representation of a guests row."""
    return {
        "id":          row.get("id"),
        "tenant_id":   row.get("tenant_id"),
        "full_name":   row.get("full_name"),
        "email":       row.get("email"),
        "phone":       row.get("phone"),
        "nationality": row.get("nationality"),
        "passport_no": row.get("passport_no"),
        "notes":       row.get("notes"),
        "created_at":  row.get("created_at"),
        "updated_at":  row.get("updated_at"),
    }
