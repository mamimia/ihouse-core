"""
Phase 156 — Property Metadata Router

CRUD API for the `properties` table — canonical store for property display info.
All UI surfaces (Operations Dashboard, Worker Mobile, Manager Booking View) read from here.

Endpoints:
    GET    /properties                  — list all properties for the tenant
    POST   /properties                  — create a new property record
    GET    /properties/{property_id}    — get a single property
    PATCH  /properties/{property_id}    — partial update (display_name, timezone, base_currency)

Invariants:
    - JWT auth required on all endpoints.
    - tenant_id always set from JWT sub — never from request body.
    - Tenant isolation: all queries scoped by (tenant_id).
    - POST returns 409 on duplicate (tenant_id, property_id).
    - GET/{property_id} returns 404 if not found.
    - PATCH returns 404 if not found.
    - Read-only path (GET) never writes to any table.
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

_VALID_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "THB", "SGD", "AED", "AUD", "CAD", "CHF",
    "CNY", "HKD", "IDR", "INR", "JPY", "KRW", "MXN", "MYR", "NZD",
    "PHP", "PLN", "SAR", "SEK", "TWD", "VND", "ZAR",
})


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

def _format_property(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":            row.get("id"),
        "property_id":   row.get("property_id"),
        "tenant_id":     row.get("tenant_id"),
        "display_name":  row.get("display_name"),
        "timezone":      row.get("timezone", "UTC"),
        "base_currency": row.get("base_currency", "USD"),
        "created_at":    row.get("created_at"),
        "updated_at":    row.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# GET /properties
# ---------------------------------------------------------------------------

@router.get(
    "/properties",
    tags=["properties"],
    summary="List all property records for this tenant (Phase 156)",
    description=(
        "Returns all property metadata records for the authenticated tenant.\\n\\n"
        "Results are sorted by `property_id` ascending.\\n\\n"
        "**Source:** `properties` table — tenant-scoped. Read-only."
    ),
    responses={
        200: {"description": "List of property records."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_properties(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /properties — list all properties for this tenant."""
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("property_id", desc=False)
            .execute()
        )
        rows: List[Dict[str, Any]] = result.data or []
        return JSONResponse(
            status_code=200,
            content={
                "tenant_id":  tenant_id,
                "count":      len(rows),
                "properties": [_format_property(r) for r in rows],
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /properties error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# POST /properties
# ---------------------------------------------------------------------------

@router.post(
    "/properties",
    tags=["properties"],
    summary="Create a new property record (Phase 156)",
    description=(
        "Create a canonical property metadata record.\\n\\n"
        "**`property_id`** must be unique within the tenant.\\n\\n"
        "**409** returned if a property with this `property_id` already exists for the tenant.\\n\\n"
        "**Invariant:** Writes only to `properties`. Never touches booking state."
    ),
    responses={
        201: {"description": "Property created successfully."},
        400: {"description": "Validation error — missing or invalid field."},
        401: {"description": "Missing or invalid JWT token."},
        409: {"description": "Property with this property_id already exists."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def create_property(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /properties

    Required body fields:
        property_id     TEXT — unique identifier for this property in the tenant
    Optional body fields:
        display_name    TEXT — human-readable name (e.g. 'Villa Sunset 3BR')
        timezone        TEXT — IANA timezone (default: UTC)
        base_currency   CHAR(3) — ISO 4217 currency code (default: USD)
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    property_id = body.get("property_id")
    if not property_id or not str(property_id).strip():
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'property_id' is required and must be a non-empty string."},
        )

    display_name  = body.get("display_name")
    timezone      = body.get("timezone", "UTC")
    base_currency = str(body.get("base_currency", "USD")).upper()

    if base_currency not in _VALID_CURRENCIES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'base_currency' must be a valid ISO 4217 code. Got: {base_currency!r}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()
        insert_data: Dict[str, Any] = {
            "tenant_id":    tenant_id,
            "property_id":  str(property_id).strip(),
            "timezone":     str(timezone) if timezone else "UTC",
            "base_currency": base_currency,
        }
        if display_name is not None:
            insert_data["display_name"] = str(display_name).strip() or None

        result = db.table("properties").insert(insert_data).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=_format_property(rows[0]))

    except Exception as exc:  # noqa: BLE001
        exc_str = str(exc).lower()
        if "unique" in exc_str or "duplicate" in exc_str or "23505" in exc_str:
            return make_error_response(
                status_code=409,
                code="CONFLICT",
                extra={"detail": (
                    f"A property with property_id='{property_id}' already exists for this tenant."
                )},
            )
        logger.exception("POST /properties error for tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /properties/{property_id}
# ---------------------------------------------------------------------------

@router.get(
    "/properties/{property_id}",
    tags=["properties"],
    summary="Get a single property record (Phase 156)",
    description=(
        "Retrieve the metadata record for a specific property.\\n\\n"
        "**404** if no property with this `property_id` exists for the tenant.\\n\\n"
        "**Source:** `properties` table — tenant-scoped. Read-only."
    ),
    responses={
        200: {"description": "Property record."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Property not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /properties/{property_id} — retrieve a specific property record."""
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows: List[Dict[str, Any]] = result.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={"detail": f"Property '{property_id}' not found for this tenant."},
            )
        return JSONResponse(status_code=200, content=_format_property(rows[0]))

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /properties/%s error for tenant=%s: %s", property_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PATCH /properties/{property_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/properties/{property_id}",
    tags=["properties"],
    summary="Update a property record (Phase 156)",
    description=(
        "Partial update of a property metadata record.\\n\\n"
        "Updatable fields: `display_name`, `timezone`, `base_currency`.\\n\\n"
        "`property_id` and `tenant_id` are immutable — they cannot be changed.\\n\\n"
        "**404** if the property does not exist for this tenant.\\n\\n"
        "**Partial update:** only supplied fields are changed — omitted fields unchanged."
    ),
    responses={
        200: {"description": "Property updated."},
        400: {"description": "Invalid or empty update body."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Property not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_property(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    PATCH /properties/{property_id}

    Partial update — any combination of: display_name, timezone, base_currency.
    Returns 404 if property not found for this tenant.
    """
    if not isinstance(body, dict) or not body:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a non-empty JSON object."},
        )

    update_data: Dict[str, Any] = {}

    if "display_name" in body:
        val = body["display_name"]
        # Allow explicit null to clear the field
        update_data["display_name"] = str(val).strip() if val is not None else None

    if "timezone" in body:
        val = body["timezone"]
        if not val or not str(val).strip():
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "'timezone' must be a non-empty string."},
            )
        update_data["timezone"] = str(val).strip()

    if "base_currency" in body:
        val = str(body["base_currency"]).upper()
        if val not in _VALID_CURRENCIES:
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"'base_currency' must be a valid ISO 4217 code. Got: {val!r}"},
            )
        update_data["base_currency"] = val

    if not update_data:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "No updatable fields provided. Allowed: display_name, timezone, base_currency."},
        )

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .update(update_data)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        rows: List[Dict[str, Any]] = result.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={"detail": f"Property '{property_id}' not found for this tenant."},
            )
        return JSONResponse(status_code=200, content=_format_property(rows[0]))

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "PATCH /properties/%s error for tenant=%s: %s", property_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
