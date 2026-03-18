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
from datetime import datetime, timezone as tz
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
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

# All updatable property fields (Phases 587-590, 844)
_PROPERTY_DETAIL_FIELDS = [
    "property_type", "city", "country", "address",  # Phase 844 — core fields
    "bedrooms", "beds", "bathrooms", "max_guests",  # Phase 844 — capacity
    "description", "source_url",  # Phase 844 — operation
    "checkin_time", "checkout_time",  # Phase 587
    "deposit_required", "deposit_amount", "deposit_currency", "deposit_method",  # Phase 588
    "door_code", "key_location", "wifi_name", "wifi_password",  # Phase 590
    "ac_instructions", "hot_water_info", "stove_instructions",
    "breaker_location", "trash_instructions", "parking_info",
    "pool_instructions", "laundry_info", "tv_info", "safe_code",
    "emergency_contact", "extra_notes",
    "maintenance_mode",  # Phase 603
    "owner_phone", "owner_email",  # Phase 844 — contact snapshot
    "amenities",  # Phase 844 — property features checklist
    "house_rules",  # Phase 589 — JSONB array of rule strings
    "cover_photo_url",  # Phase 844 — explicit hero/cover image selection
    # GPS / Location — Phase 844
    "gps_source",  # string — how GPS was obtained
    # Note: latitude and longitude are handled separately as floats below
]

# Numeric fields that require type conversion in PATCH
_PROPERTY_NUMERIC_FIELDS: Dict[str, type] = {
    "latitude": float,
    "longitude": float,
    "bedrooms": int,
    "beds": int,
    "bathrooms": float,
    "max_guests": int,
    "deposit_amount": float,
}


def _format_property(row: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "id":            row.get("id"),
        "property_id":   row.get("property_id"),
        "tenant_id":     row.get("tenant_id"),
        "display_name":  row.get("display_name"),
        "timezone":      row.get("timezone", "UTC"),
        "base_currency": row.get("base_currency", "USD"),
        # Property type + location
        "property_type": row.get("property_type"),
        "city":          row.get("city"),
        "country":       row.get("country"),
        "address":       row.get("address"),
        # Capacity
        "bedrooms":      row.get("bedrooms"),
        "beds":          row.get("beds"),
        "bathrooms":     row.get("bathrooms"),
        "max_guests":    row.get("max_guests"),
        # Operation
        "description":   row.get("description"),
        "source_url":    row.get("source_url"),
        # Phase 586 — GPS
        "latitude":      row.get("latitude"),
        "longitude":     row.get("longitude"),
        "gps_source":    row.get("gps_source"),
        # Phase 589 — House Rules
        "house_rules":   row.get("house_rules", []),
        # Phase 844 — Owner contact snapshot + amenities
        "owner_phone":   row.get("owner_phone"),
        "owner_email":   row.get("owner_email"),
        "amenities":     row.get("amenities", []),
        # Status
        "status":        row.get("status"),
        "created_at":    row.get("created_at"),
        "updated_at":    row.get("updated_at"),
    }
    # Include all detail fields
    for f in _PROPERTY_DETAIL_FIELDS:
        if f in row:
            result[f] = row[f]
    return result


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
    status: Optional[str] = Query(None, description="Filter by status: 'active', 'archived', or 'all'. Default excludes archived."),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /properties — list properties. Excludes archived by default. Use ?status=archived or ?status=all."""
    try:
        db = client if client is not None else _get_supabase_client()
        q = db.table("properties").select("*").eq("tenant_id", tenant_id)
        if status == "archived":
            q = q.eq("status", "archived")
        elif status == "all":
            pass  # no filter
        else:
            # Default: exclude archived
            q = q.neq("status", "archived")
        result = q.order("property_id", desc=False).execute()
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
# Auto-ID: configurable prefix + sequence (e.g. KPG-500, KPG-501...)
# ---------------------------------------------------------------------------

_DEFAULT_PREFIX = "KPG"
_DEFAULT_START = 500


def _next_property_id(db: Any, tenant_id: str) -> str:
    """Calculate the next sequential property ID from DB settings."""
    # Read settings (will use defaults if admin_settings table doesn't exist yet)
    try:
        config = _get_property_id_config(db, tenant_id)
    except Exception:
        config = {}
    prefix = config.get("prefix", _DEFAULT_PREFIX)
    start = config.get("start_number", _DEFAULT_START)

    result = (
        db.table("properties")
        .select("property_id")
        .eq("tenant_id", tenant_id)
        .like("property_id", f"{prefix}-%")
        .order("property_id", desc=True)
        .limit(50)
        .execute()
    )
    max_num = start - 1
    for row in (result.data or []):
        pid = row.get("property_id", "")
        parts = pid.split("-", 1)
        if len(parts) == 2 and parts[1].isdigit():
            num = int(parts[1])
            if num > max_num:
                max_num = num
    return f"{prefix}-{max_num + 1}"


@router.get(
    "/properties/next-id",
    tags=["properties"],
    summary="Get the next auto-generated property ID (KPG-XXX)",
    responses={200: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_next_property_id(tenant_id: str = Depends(jwt_auth)) -> JSONResponse:
    """Returns the next available sequential property ID."""
    try:
        db = _get_supabase_client()
        next_id = _next_property_id(db, tenant_id)
        return JSONResponse(status_code=200, content={"next_id": next_id})
    except Exception as exc:
        logger.exception("GET /properties/next-id error: %s", exc)
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
        "**`property_id`** is auto-generated (KPG-500, KPG-501, ...) if not provided.\\n\\n"
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

    Optional body fields:
        property_id     TEXT — auto-generated if not provided (KPG-500, KPG-501, ...)
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

    db = client if client is not None else _get_supabase_client()

    # Auto-generate property_id if not provided
    property_id = body.get("property_id")
    if not property_id or not str(property_id).strip():
        property_id = _next_property_id(db, tenant_id)

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
        insert_data: Dict[str, Any] = {
            "tenant_id":    tenant_id,
            "property_id":  str(property_id).strip(),
            "timezone":     str(timezone) if timezone else "UTC",
            "base_currency": base_currency,
        }
        if display_name is not None:
            insert_data["display_name"] = str(display_name).strip() or None

        # Include extra fields from body
        optional_str_fields = ["city", "country", "address", "description", "source_url",
                               "property_type", "checkin_time", "checkout_time"]
        for f in optional_str_fields:
            if f in body and body[f] is not None:
                insert_data[f] = str(body[f]).strip()

        optional_num_fields = {"latitude": float, "longitude": float,
                               "bedrooms": int, "beds": int, "bathrooms": float, "max_guests": int}
        for f, conv in optional_num_fields.items():
            if f in body and body[f] is not None:
                try:
                    insert_data[f] = conv(body[f])
                except (ValueError, TypeError):
                    pass

        # Deposit fields
        if "deposit_required" in body:
            insert_data["deposit_required"] = bool(body["deposit_required"])
        if "deposit_amount" in body and body["deposit_amount"] is not None:
            try:
                insert_data["deposit_amount"] = float(body["deposit_amount"])
            except (ValueError, TypeError):
                pass
        if "deposit_currency" in body:
            insert_data["deposit_currency"] = str(body["deposit_currency"]).upper()

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

    # Phase 587-590 + 844: Accept all property detail fields
    # String/JSON fields: pass through directly
    for field in _PROPERTY_DETAIL_FIELDS:
        if field in body:
            update_data[field] = body[field]

    # Numeric fields: require explicit type conversion
    for field, conv in _PROPERTY_NUMERIC_FIELDS.items():
        if field in body and body[field] is not None:
            try:
                update_data[field] = conv(body[field])
            except (ValueError, TypeError):
                pass  # silently skip malformed numerics
        elif field in body and body[field] is None:
            update_data[field] = None  # allow explicit clear

    if not update_data:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "No updatable fields provided."},
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


# ---------------------------------------------------------------------------
# POST /properties/{property_id}/archive
# POST /properties/{property_id}/unarchive
# ---------------------------------------------------------------------------

@router.post(
    "/properties/{property_id}/archive",
    tags=["properties"],
    summary="Archive a property",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def archive_property(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Move a property to archived status. Hidden from main list but recoverable."""
    try:
        db = _get_supabase_client()
        result = (
            db.table("properties")
            .update({
                "status": "archived",
                "archived_at": datetime.now(tz.utc).isoformat(),
                "archived_by": "admin",
            })
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Property '{property_id}' not found."})
        return JSONResponse(status_code=200, content=_format_property(rows[0]))
    except Exception as exc:
        logger.exception("archive error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/properties/{property_id}/unarchive",
    tags=["properties"],
    summary="Unarchive a property — restore to active status",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def unarchive_property(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Restore an archived property to active status. Returns to the main property list."""
    try:
        db = _get_supabase_client()
        result = (
            db.table("properties")
            .update({
                "status": "approved",
                "archived_at": None,
                "archived_by": None,
            })
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Property '{property_id}' not found."})
        return JSONResponse(status_code=200, content=_format_property(rows[0]))
    except Exception as exc:
        logger.exception("unarchive error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Property ID Settings (Admin-configurable prefix/sequence)
# ---------------------------------------------------------------------------

_SETTINGS_TABLE = "admin_settings"
_PROP_ID_SETTING_KEY = "property_id_config"


def _get_property_id_config(db: Any, tenant_id: str) -> Dict[str, Any]:
    """Get or create the property ID configuration for this tenant."""
    result = (
        db.table(_SETTINGS_TABLE)
        .select("*")
        .eq("tenant_id", tenant_id)
        .eq("setting_key", _PROP_ID_SETTING_KEY)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    if rows:
        import json as _json
        val = rows[0].get("setting_value", "{}")
        if isinstance(val, str):
            return _json.loads(val)
        return val
    return {"prefix": "KPG", "start_number": 500}


@router.get(
    "/admin/property-id-settings",
    tags=["admin"],
    summary="Get property ID auto-generation settings",
    responses={200: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_id_settings(
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    try:
        db = _get_supabase_client()
        config = _get_property_id_config(db, tenant_id)
        # Also calculate what the next ID would be
        next_id = _next_property_id(db, tenant_id)
        return JSONResponse(status_code=200, content={
            "prefix": config.get("prefix", "KPG"),
            "start_number": config.get("start_number", 500),
            "next_id": next_id,
            "note": "Property IDs are immutable once created and are never reused.",
        })
    except Exception as exc:
        logger.exception("get property-id-settings error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.put(
    "/admin/property-id-settings",
    tags=["admin"],
    summary="Update property ID auto-generation settings",
    responses={200: {}, 400: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_property_id_settings(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    """Set the prefix and start_number for auto-generated property IDs."""
    import json as _json
    prefix = str(body.get("prefix", "KPG")).upper().strip()
    start_number = body.get("start_number", 500)

    if not prefix or len(prefix) > 10:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "prefix must be 1-10 characters."})
    if not isinstance(start_number, int) or start_number < 1:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "start_number must be a positive integer."})

    try:
        db = _get_supabase_client()
        config_json = _json.dumps({"prefix": prefix, "start_number": start_number})
        # Upsert
        existing = (
            db.table(_SETTINGS_TABLE)
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("setting_key", _PROP_ID_SETTING_KEY)
            .limit(1)
            .execute()
        )
        if existing.data:
            db.table(_SETTINGS_TABLE).update({
                "setting_value": config_json,
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            db.table(_SETTINGS_TABLE).insert({
                "tenant_id": tenant_id,
                "setting_key": _PROP_ID_SETTING_KEY,
                "setting_value": config_json,
            }).execute()

        next_id = _next_property_id(db, tenant_id)
        return JSONResponse(status_code=200, content={
            "prefix": prefix,
            "start_number": start_number,
            "next_id": next_id,
            "note": "Property IDs are immutable once created and are never reused.",
        })
    except Exception as exc:
        logger.exception("update property-id-settings error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
