"""
Phase 801 — Property Config & Channel Mapping Composite Endpoint

Composite read-only endpoints that return property metadata together
with its OTA channel mappings in a single response.

Endpoints:
    GET /admin/property-config
                        — list all properties with their channel mappings
    GET /admin/property-config/{property_id}
                        — single property + its channel mappings

Invariants:
    - JWT auth required on all endpoints.
    - Tenant isolation: tenant_id set from JWT sub — never from body.
    - Read-only: no writes to any table.
    - Source tables: `properties` + `property_channel_map`.
    - apply_envelope is NOT involved — this is config, not canonical booking state.
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


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Row formatting helpers
# ---------------------------------------------------------------------------

def _format_property(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "property_id":   row.get("property_id"),
        "tenant_id":     row.get("tenant_id"),
        "display_name":  row.get("display_name"),
        "timezone":      row.get("timezone", "UTC"),
        "base_currency": row.get("base_currency", "USD"),
        "status":        row.get("status"),
        "property_type": row.get("property_type"),
        "city":          row.get("city"),
        "country":       row.get("country"),
        "max_guests":    row.get("max_guests"),
        "bedrooms":      row.get("bedrooms"),
        "beds":          row.get("beds"),
        "bathrooms":     row.get("bathrooms"),
        "address":       row.get("address"),
        "created_at":    row.get("created_at"),
        "updated_at":    row.get("updated_at"),
    }


def _format_channel(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":             row.get("id"),
        "provider":       row.get("provider"),
        "external_id":    row.get("external_id"),
        "inventory_type": row.get("inventory_type", "single_unit"),
        "sync_mode":      row.get("sync_mode", "api_first"),
        "enabled":        row.get("enabled", True),
        "created_at":     row.get("created_at"),
        "updated_at":     row.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# GET /admin/property-config/{property_id}
# ---------------------------------------------------------------------------

@router.get(
    "/admin/property-config/{property_id}",
    tags=["property-config"],
    summary="Get property config with channel mappings (Phase 801)",
    description=(
        "Composite endpoint: returns the property metadata record **plus** "
        "all its OTA channel mappings in a single response.\\n\\n"
        "Saves a second roundtrip vs separate `/properties/{id}` + "
        "`/admin/properties/{id}/channels` calls.\\n\\n"
        "**404** if the property does not exist for this tenant."
    ),
    responses={
        200: {"description": "Property config with channel mappings."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Property not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_property_config(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/property-config/{property_id}

    Returns: { property: {...}, channels: { count, mappings: [...] } }
    """
    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch property
        prop_result = (
            db.table("properties")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        prop_rows: List[Dict[str, Any]] = prop_result.data or []
        if not prop_rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={"detail": f"Property '{property_id}' not found for this tenant."},
            )

        # Fetch channel mappings
        chan_result = (
            db.table("property_channel_map")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("provider", desc=False)
            .execute()
        )
        chan_rows: List[Dict[str, Any]] = chan_result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "property": _format_property(prop_rows[0]),
                "channels": {
                    "count": len(chan_rows),
                    "mappings": [_format_channel(r) for r in chan_rows],
                },
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/property-config/%s error for tenant=%s: %s",
            property_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/property-config
# ---------------------------------------------------------------------------

@router.get(
    "/admin/property-config",
    tags=["property-config"],
    summary="List all properties with channel mappings (Phase 801)",
    description=(
        "Composite endpoint: returns **all** properties for the tenant, "
        "each with its OTA channel mappings.\\n\\n"
        "Equivalent to calling `/properties` + `/admin/properties/{id}/channels` "
        "for every property — but in a single request."
    ),
    responses={
        200: {"description": "All properties with their channel configs."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_property_configs(
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/property-config

    Returns: { tenant_id, count, properties: [{ property, channels }] }
    """
    try:
        db = client if client is not None else _get_supabase_client()

        # Fetch all properties
        prop_result = (
            db.table("properties")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("property_id", desc=False)
            .execute()
        )
        prop_rows: List[Dict[str, Any]] = prop_result.data or []

        # Fetch all channel mappings for this tenant
        chan_result = (
            db.table("property_channel_map")
            .select("*")
            .eq("tenant_id", tenant_id)
            .order("provider", desc=False)
            .execute()
        )
        chan_rows: List[Dict[str, Any]] = chan_result.data or []

        # Group channels by property_id
        channels_by_prop: Dict[str, List[Dict[str, Any]]] = {}
        for ch in chan_rows:
            pid = ch.get("property_id", "")
            channels_by_prop.setdefault(pid, []).append(ch)

        # Build composite response
        items = []
        for prop in prop_rows:
            pid = prop.get("property_id", "")
            prop_channels = channels_by_prop.get(pid, [])
            items.append({
                "property": _format_property(prop),
                "channels": {
                    "count": len(prop_channels),
                    "mappings": [_format_channel(c) for c in prop_channels],
                },
            })

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "count": len(items),
                "properties": items,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/property-config error for tenant=%s: %s",
            tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
