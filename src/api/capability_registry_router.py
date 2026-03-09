"""
Phase 136 — Provider Capability Registry API

Read-only + admin-upsert API for `provider_capability_registry`.

The registry is **global** (not tenant-scoped). It defines what each OTA
provider supports for outbound availability sync:
  - Does it have a write API? (supports_api_write)
  - Does it support iCal push? (supports_ical_push)
  - What tier is it? (A/B/C/D)
  - What are the rate limits and auth method?

This data drives the Outbound Sync Trigger (Phase 137): before sending any
availability update, the trigger consults this registry to decide which
strategy to use for each provider.

Endpoints:
    GET  /admin/registry/providers               — list all providers
    GET  /admin/registry/providers/{provider}    — single provider detail
    PUT  /admin/registry/providers/{provider}    — upsert provider record (admin)

Tiers:
    A — Full write API (api_first capable)
    B — iCal push only
    C — iCal pull only (read requests from provider)
    D — Read-only / no inventory sync

Invariants:
    - GET endpoints: JWT required, read-only, no writes.
    - PUT endpoint: JWT required. Writes only to provider_capability_registry.
    - apply_envelope is NOT involved — this is static config, not canonical state.
    - provider name is case-folded to lowercase on write.
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

_VALID_TIERS = frozenset({"A", "B", "C", "D"})
_VALID_AUTH_METHODS = frozenset({"oauth2", "api_key", "basic", "none"})


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

_SELECT_COLS = (
    "id, provider, tier, supports_api_write, supports_ical_push, supports_ical_pull, "
    "rate_limit_per_min, auth_method, write_api_base_url, notes, created_at, updated_at"
)


def _format_record(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id":                  row.get("id"),
        "provider":            row.get("provider"),
        "tier":                row.get("tier"),
        "supports_api_write":  row.get("supports_api_write", False),
        "supports_ical_push":  row.get("supports_ical_push", False),
        "supports_ical_pull":  row.get("supports_ical_pull", True),
        "rate_limit_per_min":  row.get("rate_limit_per_min", 60),
        "auth_method":         row.get("auth_method", "none"),
        "write_api_base_url":  row.get("write_api_base_url"),
        "notes":               row.get("notes"),
        "created_at":          row.get("created_at"),
        "updated_at":          row.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# GET /admin/registry/providers
# ---------------------------------------------------------------------------

@router.get(
    "/admin/registry/providers",
    tags=["registry"],
    summary="List all providers in capability registry (Phase 136)",
    description=(
        "Returns all OTA providers registered in the `provider_capability_registry`.\\n\\n"
        "**Global:** not tenant-scoped — same data for all tenants.\\n\\n"
        "**Filters:** `tier` (A/B/C/D), `supports_api_write` (true/false).\\n\\n"
        "This is the data source the Outbound Sync Trigger consults before "
        "choosing api_first vs ical_fallback for each channel.\\n\\n"
        "**Source:** `provider_capability_registry`. Read-only."
    ),
    responses={
        200: {"description": "List of providers with capability details."},
        400: {"description": "Invalid filter value."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_providers(
    tier: Optional[str] = None,
    supports_api_write: Optional[bool] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/registry/providers?tier=A&supports_api_write=true

    Lists all providers, optionally filtered by tier and/or write capability.
    Global table — not tenant-scoped.
    """
    if tier is not None and tier not in _VALID_TIERS:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'tier' must be one of: {sorted(_VALID_TIERS)}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        query = (
            db.table("provider_capability_registry")
            .select(_SELECT_COLS)
            .order("tier", desc=False)
        )

        if tier is not None:
            query = query.eq("tier", tier)

        if supports_api_write is not None:
            query = query.eq("supports_api_write", supports_api_write)

        result = query.execute()
        rows: List[Dict[str, Any]] = result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/registry/providers error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    providers = [_format_record(r) for r in rows]
    return JSONResponse(
        status_code=200,
        content={
            "total":               len(providers),
            "tier_filter":         tier,
            "api_write_filter":    supports_api_write,
            "providers":           providers,
        },
    )


# ---------------------------------------------------------------------------
# GET /admin/registry/providers/{provider}
# ---------------------------------------------------------------------------

@router.get(
    "/admin/registry/providers/{provider}",
    tags=["registry"],
    summary="Get single provider capability record (Phase 136)",
    description=(
        "Retrieve the capability record for a specific OTA provider.\\n\\n"
        "**404** if the provider is not registered.\\n\\n"
        "Provider names are case-insensitive (folded to lowercase at lookup time)."
    ),
    responses={
        200: {"description": "Full capability record for the provider."},
        401: {"description": "Missing or invalid JWT token."},
        404: {"description": "Provider not registered in the capability registry."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_provider(
    provider: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    GET /admin/registry/providers/{provider}

    Returns capability record for the named provider (case-insensitive).
    404 if not found.
    """
    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("provider_capability_registry")
            .select(_SELECT_COLS)
            .eq("provider", provider.lower().strip())
            .limit(1)
            .execute()
        )
        rows: List[Dict[str, Any]] = result.data or []

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/registry/providers/%s error: %s", provider, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    if not rows:
        return make_error_response(
            status_code=404,
            code="NOT_FOUND",
            extra={"detail": f"Provider '{provider}' is not registered in the capability registry."},
        )

    return JSONResponse(status_code=200, content=_format_record(rows[0]))


# ---------------------------------------------------------------------------
# PUT /admin/registry/providers/{provider}
# ---------------------------------------------------------------------------

@router.put(
    "/admin/registry/providers/{provider}",
    tags=["registry"],
    summary="Upsert provider capability record (Phase 136)",
    description=(
        "Insert or update the capability record for a specific OTA provider.\\n\\n"
        "**Idempotent:** safe to call multiple times — if the provider exists, "
        "its fields are updated; if not, a new record is created.\\n\\n"
        "**Required fields:** `tier`.\\n\\n"
        "**Note:** provider name is stored lowercase.\\n\\n"
        "Use this to update `write_api_base_url` after enrolling in a partner program, "
        "or to mark `supports_api_write` once API credentials are provisioned."
    ),
    responses={
        200: {"description": "Provider record created or updated."},
        400: {"description": "Invalid field value."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_provider(
    provider: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    PUT /admin/registry/providers/{provider}

    Upsert (insert-or-update) a provider capability record.
    Required: tier. All other fields optional.
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    tier = body.get("tier")
    if tier not in _VALID_TIERS:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'tier' is required and must be one of: {sorted(_VALID_TIERS)}"},
        )

    auth_method = body.get("auth_method", "none")
    if auth_method not in _VALID_AUTH_METHODS:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'auth_method' must be one of: {sorted(_VALID_AUTH_METHODS)}"},
        )

    for bool_field in ("supports_api_write", "supports_ical_push", "supports_ical_pull"):
        if bool_field in body and not isinstance(body[bool_field], bool):
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": f"'{bool_field}' must be a boolean."},
            )

    if "rate_limit_per_min" in body:
        val = body["rate_limit_per_min"]
        if not isinstance(val, int) or val < 0:
            return make_error_response(
                status_code=400,
                code=ErrorCode.VALIDATION_ERROR,
                extra={"detail": "'rate_limit_per_min' must be a non-negative integer."},
            )

    provider_key = provider.lower().strip()
    record: Dict[str, Any] = {
        "provider":            provider_key,
        "tier":                tier,
        "supports_api_write":  body.get("supports_api_write", False),
        "supports_ical_push":  body.get("supports_ical_push", False),
        "supports_ical_pull":  body.get("supports_ical_pull", True),
        "rate_limit_per_min":  body.get("rate_limit_per_min", 60),
        "auth_method":         auth_method,
    }

    if "write_api_base_url" in body:
        record["write_api_base_url"] = body["write_api_base_url"]
    if "notes" in body:
        record["notes"] = body["notes"]

    try:
        db = client if client is not None else _get_supabase_client()

        result = (
            db.table("provider_capability_registry")
            .upsert(record, on_conflict="provider")
            .execute()
        )

        rows: List[Dict[str, Any]] = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

        return JSONResponse(status_code=200, content=_format_record(rows[0]))

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "PUT /admin/registry/providers/%s error: %s", provider, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
