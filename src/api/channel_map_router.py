"""
Phase 135 — Property-Channel Mapping Foundation

CRUD API for the `property_channel_map` table.
This is the master inventory linkage for the Outbound Sync Layer.

Endpoints:
    POST   /admin/properties/{property_id}/channels
                        — register a new channel mapping for a property
    GET    /admin/properties/{property_id}/channels
                        — list all channel mappings for a property
    PATCH  /admin/properties/{property_id}/channels/{provider}
                        — update sync_mode, external_id, or enabled flag
    DELETE /admin/properties/{property_id}/channels/{provider}
                        — remove a channel mapping

Schema (property_channel_map):
    id              BIGSERIAL PRIMARY KEY
    tenant_id       TEXT                        (from JWT)
    property_id     TEXT                        (path param)
    provider        TEXT                        (from body)
    external_id     TEXT                        (provider's listing ID)
    inventory_type  TEXT  DEFAULT 'single_unit' (single_unit|multi_unit|shared)
    sync_mode       TEXT  DEFAULT 'api_first'   (api_first|ical_fallback|disabled)
    enabled         BOOLEAN DEFAULT true
    created_at      TIMESTAMPTZ
    updated_at      TIMESTAMPTZ

Invariants:
    - JWT auth required on all endpoints.
    - Tenant isolation: tenant_id set from JWT sub — never from body.
    - Read-only query path: GET never writes to any table.
    - Write path (POST/PATCH/DELETE) only writes to property_channel_map.
    - apply_envelope is NOT involved — this is outbound config, not canonical booking state.
    - Duplicate (tenant_id, property_id, provider) returns 409 CONFLICT on POST.
    - Non-existent mapping returns 404 on GET/{provider}, PATCH, DELETE.

Provider enum is open (not validated server-side) — new providers can be
added without code changes. Validation is the caller's responsibility.
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

_VALID_INVENTORY_TYPES = frozenset({"single_unit", "multi_unit", "shared"})
_VALID_SYNC_MODES = frozenset({"api_first", "ical_fallback", "disabled"})


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

def _format_mapping(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":             row.get("id"),
        "tenant_id":      row.get("tenant_id"),
        "property_id":    row.get("property_id"),
        "provider":       row.get("provider"),
        "external_id":    row.get("external_id"),
        "inventory_type": row.get("inventory_type", "single_unit"),
        "sync_mode":      row.get("sync_mode", "api_first"),
        "enabled":        row.get("enabled", True),
        "created_at":     row.get("created_at"),
        "updated_at":     row.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# POST /admin/properties/{property_id}/channels
# ---------------------------------------------------------------------------

@router.post(
    "/admin/properties/{property_id}/channels",
    tags=["channel-map"],
    summary="Register a channel mapping for a property (Phase 135)",
    description=(
        "Register an external OTA listing ID for an internal property.\\n\\n"
        "This is the **outbound sync foundation** — without a mapping entry, "
        "the sync layer does not know which external listings to lock when a "
        "booking is received.\\n\\n"
        "**`sync_mode`** controls the outbound strategy:\\n"
        "- `api_first` — use the provider's write API (Tier A/B)\\n"
        "- `ical_fallback` — use iCal feed (degraded mode)\\n"
        "- `disabled` — no outbound sync for this channel\\n\\n"
        "**409** returned if a mapping for this (property_id, provider) already exists.\\n\\n"
        "**Invariant:** Writes only to `property_channel_map`. Never touches booking state."
    ),
    responses={
        201: {"description": "Mapping registered successfully."},
        400: {"description": "Invalid body field value."},
        401: {"description": "Missing or invalid JWT token."},
        409: {"description": "Mapping for this (property_id, provider) already exists."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def register_channel_mapping(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /admin/properties/{property_id}/channels

    Body fields:
        provider      TEXT (required)
        external_id   TEXT (required)
        inventory_type TEXT (optional, default: single_unit)
        sync_mode     TEXT (optional, default: api_first)
        enabled       BOOLEAN (optional, default: true)
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    provider = body.get("provider")
    external_id = body.get("external_id")

    if not provider or not str(provider).strip():
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'provider' is required and must be a non-empty string."},
        )

    if not external_id or not str(external_id).strip():
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'external_id' is required and must be a non-empty string."},
        )

    inventory_type = body.get("inventory_type", "single_unit")
    if inventory_type not in _VALID_INVENTORY_TYPES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'inventory_type' must be one of: {sorted(_VALID_INVENTORY_TYPES)}"},
        )

    sync_mode = body.get("sync_mode", "api_first")
    if sync_mode not in _VALID_SYNC_MODES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'sync_mode' must be one of: {sorted(_VALID_SYNC_MODES)}"},
        )

    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'enabled' must be a boolean."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("property_channel_map")
            .insert({
                "tenant_id":      tenant_id,
                "property_id":    property_id,
                "provider":       str(provider).strip(),
                "external_id":    str(external_id).strip(),
                "inventory_type": inventory_type,
                "sync_mode":      sync_mode,
                "enabled":        enabled,
            })
            .execute()
        )

        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

        return JSONResponse(status_code=201, content=_format_mapping(rows[0]))

    except Exception as exc:  # noqa: BLE001
        exc_str = str(exc).lower()
        # Detect unique constraint violation (duplicate mapping)
        if "unique" in exc_str or "duplicate" in exc_str or "23505" in exc_str:
            return make_error_response(
                status_code=409,
                code="CONFLICT",
                extra={
                    "detail": (
                        f"A mapping for property_id='{property_id}' provider='{provider}' "
                        f"already exists for this tenant."
                    )
                },
            )
        logger.exception(
            "POST /admin/properties/%s/channels error for tenant=%s: %s",
            property_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# GET /admin/properties/{property_id}/channels
# ---------------------------------------------------------------------------

@router.get(
    "/admin/properties/{property_id}/channels",
    tags=["channel-map"],
    summary="List channel mappings for a property (Phase 135)",
    description=(
        "List all OTA channel mappings registered for an internal property.\\n\\n"
        "Returns all providers mapped to this property, regardless of `enabled` status.\\n\\n"
        "**Source:** `property_channel_map` — tenant-scoped. Read-only."
    ),
    responses={
        200: {"description": "List of channel mappings for the property."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_channel_mappings(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/properties/{property_id}/channels

    Returns all mappings for property_id under this tenant.
    Empty list (not 404) if no mappings exist.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("property_channel_map")
            .select("*")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .order("created_at", desc=False)
            .execute()
        )

        rows: List[Dict[str, Any]] = result.data or []
        mappings = [_format_mapping(r) for r in rows]

        return JSONResponse(
            status_code=200,
            content={
                "property_id": property_id,
                "tenant_id":   tenant_id,
                "count":       len(mappings),
                "mappings":    mappings,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /admin/properties/%s/channels error for tenant=%s: %s",
            property_id, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# PATCH /admin/properties/{property_id}/channels/{provider}
# ---------------------------------------------------------------------------

@router.patch(
    "/admin/properties/{property_id}/channels/{provider}",
    tags=["channel-map"],
    summary="Update a channel mapping (Phase 135)",
    description=(
        "Update an existing channel mapping for a (property_id, provider) pair.\\n\\n"
        "Updatable fields: `external_id`, `sync_mode`, `inventory_type`, `enabled`.\\n\\n"
        "**404** if the mapping does not exist.\\n\\n"
        "**Partial update:** only supplied fields are changed — omitted fields unchanged."
    ),
    responses={
        200: {"description": "Mapping updated."},
        400: {"description": "Invalid field value."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Mapping not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_channel_mapping(
    property_id: str,
    provider: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    PATCH /admin/properties/{property_id}/channels/{provider}

    Partial update — any combination of: external_id, sync_mode, inventory_type, enabled.
    Returns 404 if (tenant_id, property_id, provider) not found.
    """
    if not isinstance(body, dict) or not body:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a non-empty JSON object."},
        )

    update_data: Dict[str, Any] = {}

    if "external_id" in body:
        val = body["external_id"]
        if not val or not str(val).strip():
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "'external_id' must be a non-empty string."},
            )
        update_data["external_id"] = str(val).strip()

    if "sync_mode" in body:
        val = body["sync_mode"]
        if val not in _VALID_SYNC_MODES:
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"'sync_mode' must be one of: {sorted(_VALID_SYNC_MODES)}"},
            )
        update_data["sync_mode"] = val

    if "inventory_type" in body:
        val = body["inventory_type"]
        if val not in _VALID_INVENTORY_TYPES:
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"'inventory_type' must be one of: {sorted(_VALID_INVENTORY_TYPES)}"},
            )
        update_data["inventory_type"] = val

    if "enabled" in body:
        val = body["enabled"]
        if not isinstance(val, bool):
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "'enabled' must be a boolean."},
            )
        update_data["enabled"] = val

    if not update_data:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "No updatable fields provided. Allowed: external_id, sync_mode, inventory_type, enabled."},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("property_channel_map")
            .update(update_data)
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("provider", provider)
            .execute()
        )

        rows: List[Dict[str, Any]] = result.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={
                    "detail": (
                        f"No mapping found for property_id='{property_id}' "
                        f"provider='{provider}' for this tenant."
                    )
                },
            )

        return JSONResponse(status_code=200, content=_format_mapping(rows[0]))

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "PATCH /admin/properties/%s/channels/%s error for tenant=%s: %s",
            property_id, provider, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# DELETE /admin/properties/{property_id}/channels/{provider}
# ---------------------------------------------------------------------------

@router.delete(
    "/admin/properties/{property_id}/channels/{provider}",
    tags=["channel-map"],
    summary="Remove a channel mapping (Phase 135)",
    description=(
        "Remove the channel mapping for a (property_id, provider) pair.\\n\\n"
        "**404** if the mapping does not exist.\\n\\n"
        "**Warning:** Removing a mapping means the outbound sync layer "
        "will no longer send availability updates to this provider for this property."
    ),
    responses={
        200: {"description": "Mapping removed."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Mapping not found."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def delete_channel_mapping(
    property_id: str,
    provider: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    DELETE /admin/properties/{property_id}/channels/{provider}

    Removes the channel mapping. Returns 404 if not found.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("property_channel_map")
            .delete()
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("provider", provider)
            .execute()
        )

        rows: List[Dict[str, Any]] = result.data or []
        if not rows:
            return make_error_response(
                status_code=404,
                code="NOT_FOUND",
                extra={
                    "detail": (
                        f"No mapping found for property_id='{property_id}' "
                        f"provider='{provider}' for this tenant."
                    )
                },
            )

        return JSONResponse(
            status_code=200,
            content={
                "deleted":     True,
                "property_id": property_id,
                "provider":    str(provider),
                "tenant_id":   tenant_id,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "DELETE /admin/properties/%s/channels/%s error for tenant=%s: %s",
            property_id, provider, tenant_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
