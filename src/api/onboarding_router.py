"""
Phase 214 — Property Onboarding Wizard API

Guided multi-step flow for registering a new property end-to-end.

Steps (stateless — each step is idempotent and self-contained):
    Step 1 — Property Metadata
        POST /onboarding/start
        Creates the property record (or confirms existing) via `properties` table.

    Step 2 — Channel Mappings
        POST /onboarding/{property_id}/channels
        Registers OTA-to-property channel mappings in `channel_map` table.
        Multiple mappings may be submitted in a single call.

    Step 3 — Worker Assignments
        POST /onboarding/{property_id}/workers
        Registers notification channels (LINE, WhatsApp, Telegram, SMS, email)
        for workers assigned to this property in `notification_channels` table.

    Status Query
        GET /onboarding/{property_id}/status
        Summarises the onboarding completion state across all three steps.

Design:
    - Stateless: no `onboarding_sessions` table. Each step is independently
      idempotent — safe to call multiple times (upsert semantics).
    - Property creation (Step 1) delegates to the existing `properties` table.
    - Channel mappings (Step 2) upsert into `channel_map` (provider → property).
    - Worker assignments (Step 3) upsert into `notification_channels`.
    - Status is derived dynamically from the 3 underlying tables.

Invariants (Phase 214):
    - JWT auth required on all endpoints.
    - tenant_id always from JWT, never from request body.
    - Tenant isolation: all reads/writes scoped by tenant_id.
    - POST /onboarding/start returns 409 if property_id already locked
      (i.e. has active bookings — safety gate).
    - All steps return partial success with detail[] array listing any row-level errors.
    - Status step returns 200 always — never 404 (reflects zero completions if new).
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
router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_CURRENCIES = frozenset({
    "USD", "EUR", "GBP", "THB", "SGD", "AED", "AUD", "CAD", "CHF",
    "CNY", "HKD", "IDR", "INR", "JPY", "KRW", "MXN", "MYR", "NZD",
    "PHP", "PLN", "SAR", "SEK", "TWD", "VND", "ZAR",
})

_VALID_CHANNEL_TYPES = frozenset({"line", "whatsapp", "telegram", "sms", "email", "fcm"})

_VALID_OTA_PROVIDERS = frozenset({
    "airbnb", "booking", "vrbo", "agoda", "expedia", "trip", "despegar",
    "rakuten", "ctrip", "traveloka", "klook", "ical", "direct",
})

# ---------------------------------------------------------------------------
# Step 1 — POST /onboarding/start
# ---------------------------------------------------------------------------

@router.post(
    "/start",
    tags=["onboarding"],
    summary="Step 1 — Create property and begin onboarding (Phase 214)",
    description=(
        "Creates a new property record and begins the onboarding flow.\\n\\n"
        "Idempotent: if the property already exists, returns its current record with "
        "`already_exists: true`.\\n\\n"
        "**Safety gate:** Returns 409 if the property_id exists AND has active bookings "
        "— the property is live and cannot be re-onboarded.\\n\\n"
        "**Next step:** POST /onboarding/{property_id}/channels"
    ),
    responses={
        201: {"description": "Property created. Onboarding started."},
        200: {"description": "Property already exists. Onboarding can continue."},
        400: {"description": "Validation error."},
        401: {"description": "Missing or invalid JWT token."},
        409: {"description": "Property has active bookings — cannot re-onboard."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def onboarding_start(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /onboarding/start — Step 1: property metadata.

    Required:
        property_id     TEXT
    Optional:
        display_name    TEXT
        timezone        TEXT (IANA, default: UTC)
        base_currency   CHAR(3) ISO 4217 (default: USD)
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    property_id = str(body.get("property_id") or "").strip()
    if not property_id:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'property_id' is required."},
        )

    display_name  = body.get("display_name")
    timezone      = str(body.get("timezone") or "UTC")
    base_currency = str(body.get("base_currency") or "USD").upper()

    # QuickStart extended fields (all optional)
    property_type   = body.get("property_type")
    city            = body.get("city")
    country         = body.get("country")
    max_guests      = body.get("max_guests")
    bedrooms        = body.get("bedrooms")
    beds            = body.get("beds")
    bathrooms       = body.get("bathrooms")
    address         = body.get("address")
    description     = body.get("description")
    source_url      = body.get("source_url")
    source_platform = body.get("source_platform")

    if base_currency not in _VALID_CURRENCIES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": f"'base_currency' must be a valid ISO 4217 code. Got: {base_currency!r}"},
        )

    try:
        db = client if client is not None else _get_supabase_client()

        # Check if already exists
        existing = (
            db.table("properties")
            .select("property_id, display_name, timezone, base_currency, created_at")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        existing_rows = existing.data or []

        if existing_rows:
            # Safety gate: check for active bookings
            bookings_check = (
                db.table("booking_state")
                .select("booking_ref", count="exact")
                .eq("tenant_id", tenant_id)
                .eq("property_id", property_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            active_count = (bookings_check.count or 0) if hasattr(bookings_check, "count") else len(bookings_check.data or [])

            if active_count > 0:
                return make_error_response(
                    status_code=409,
                    code="CONFLICT",
                    extra={
                        "detail": (
                            f"Property '{property_id}' already exists AND has active bookings. "
                            "Cannot re-onboard a live property."
                        )
                    },
                )
            # Property exists, no active bookings → can continue onboarding
            row = existing_rows[0]
            return JSONResponse(
                status_code=200,
                content={
                    "property_id":    row.get("property_id"),
                    "display_name":   row.get("display_name"),
                    "timezone":       row.get("timezone", "UTC"),
                    "base_currency":  row.get("base_currency", "USD"),
                    "created_at":     row.get("created_at"),
                    "already_exists": True,
                    "next_step":      f"POST /onboarding/{property_id}/channels",
                },
            )

        # Create fresh property with all QuickStart fields
        insert_data: Dict[str, Any] = {
            "tenant_id":     tenant_id,
            "property_id":   property_id,
            "timezone":      timezone,
            "base_currency": base_currency,
        }
        if display_name is not None:
            insert_data["display_name"] = str(display_name).strip() or None
        if property_type:
            insert_data["property_type"] = str(property_type).strip()
        if city:
            insert_data["city"] = str(city).strip()
        if country:
            insert_data["country"] = str(country).strip()
        if max_guests is not None:
            try:
                insert_data["max_guests"] = int(max_guests)
            except (ValueError, TypeError):
                pass
        if bedrooms is not None:
            try:
                insert_data["bedrooms"] = int(bedrooms)
            except (ValueError, TypeError):
                pass
        if beds is not None:
            try:
                insert_data["beds"] = int(beds)
            except (ValueError, TypeError):
                pass
        if bathrooms is not None:
            try:
                insert_data["bathrooms"] = float(bathrooms)
            except (ValueError, TypeError):
                pass
        if address:
            insert_data["address"] = str(address).strip()
        if description:
            insert_data["description"] = str(description).strip()
        if source_url:
            insert_data["source_url"] = str(source_url).strip()
        if source_platform:
            insert_data["source_platform"] = str(source_platform).strip()

        result = db.table("properties").insert(insert_data).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

        row = rows[0]
        return JSONResponse(
            status_code=201,
            content={
                "property_id":    row.get("property_id"),
                "display_name":   row.get("display_name"),
                "timezone":       row.get("timezone", "UTC"),
                "base_currency":  row.get("base_currency", "USD"),
                "property_type":  row.get("property_type"),
                "city":           row.get("city"),
                "country":        row.get("country"),
                "max_guests":     row.get("max_guests"),
                "bedrooms":       row.get("bedrooms"),
                "beds":           row.get("beds"),
                "bathrooms":      row.get("bathrooms"),
                "address":        row.get("address"),
                "source_url":     row.get("source_url"),
                "source_platform": row.get("source_platform"),
                "created_at":     row.get("created_at"),
                "already_exists": False,
                "next_step":      f"POST /onboarding/{property_id}/channels",
            },
        )

    except Exception as exc:  # noqa: BLE001
        exc_str = str(exc).lower()
        if "unique" in exc_str or "duplicate" in exc_str or "23505" in exc_str:
            return make_error_response(
                status_code=409,
                code="CONFLICT",
                extra={"detail": f"Property '{property_id}' already exists."},
            )
        logger.exception("POST /onboarding/start error tenant=%s: %s", tenant_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Step 2 — POST /onboarding/{property_id}/channels
# ---------------------------------------------------------------------------

@router.post(
    "/{property_id}/channels",
    tags=["onboarding"],
    summary="Step 2 — Register OTA channel mappings for the property (Phase 214)",
    description=(
        "Registers OTA provider ↔ property channel mappings in `channel_map`.\\n\\n"
        "Accepts a list of `{provider, external_channel_id}` objects.\\n\\n"
        "Idempotent (upsert): existing mappings are updated, new ones are inserted.\\n\\n"
        "Returns `registered` (success count) and `errors` (any row-level failures).\\n\\n"
        "**Next step:** POST /onboarding/{property_id}/workers"
    ),
    responses={
        200: {"description": "Channel mappings registered."},
        400: {"description": "Validation error."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def onboarding_channels(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /onboarding/{property_id}/channels — Step 2: OTA channel mappings.

    Body:
        channels: [
            { "provider": "airbnb", "external_channel_id": "AIRBNB-CH-001" },
            { "provider": "booking", "external_channel_id": "BDC-CH-002" }
        ]
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    channels = body.get("channels")
    if not channels or not isinstance(channels, list):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'channels' must be a non-empty list of {provider, external_channel_id}."},
        )

    registered: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    try:
        db = client if client is not None else _get_supabase_client()

        for idx, ch in enumerate(channels):
            if not isinstance(ch, dict):
                errors.append({"index": idx, "error": "Item must be a JSON object."})
                continue

            provider = str(ch.get("provider") or "").lower().strip()
            ext_id   = str(ch.get("external_channel_id") or "").strip()

            if not provider:
                errors.append({"index": idx, "error": "Missing 'provider'."})
                continue
            if provider not in _VALID_OTA_PROVIDERS:
                errors.append({"index": idx, "error": f"Unknown provider '{provider}'."})
                continue
            if not ext_id:
                errors.append({"index": idx, "error": "Missing 'external_channel_id'."})
                continue

            try:
                row_data = {
                    "tenant_id":           tenant_id,
                    "property_id":         property_id,
                    "provider":            provider,
                    "external_channel_id": ext_id,
                    "active":              True,
                }
                # Upsert on (tenant_id, property_id, provider)
                db.table("channel_map").upsert(
                    row_data,
                    on_conflict="tenant_id,property_id,provider",
                ).execute()
                registered.append({"provider": provider, "external_channel_id": ext_id})

            except Exception as row_exc:  # noqa: BLE001
                errors.append({"index": idx, "provider": provider, "error": str(row_exc)[:120]})

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /onboarding/%s/channels error tenant=%s: %s", property_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    return JSONResponse(
        status_code=200,
        content={
            "property_id": property_id,
            "registered":  registered,
            "errors":      errors,
            "next_step":   f"POST /onboarding/{property_id}/workers",
        },
    )


# ---------------------------------------------------------------------------
# Step 3 — POST /onboarding/{property_id}/workers
# ---------------------------------------------------------------------------

@router.post(
    "/{property_id}/workers",
    tags=["onboarding"],
    summary="Step 3 — Assign workers and register notification channels (Phase 214)",
    description=(
        "Registers worker notification channels for the property.\\n\\n"
        "Accepts a list of `{user_id, channel_type, channel_id}` objects.\\n\\n"
        "Idempotent (upsert): existing channels are updated.\\n\\n"
        "Returns `registered` and `errors`.\\n\\n"
        "**Onboarding is complete after this step.** "
        "Check: GET /onboarding/{property_id}/status"
    ),
    responses={
        200: {"description": "Workers registered."},
        400: {"description": "Validation error."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def onboarding_workers(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /onboarding/{property_id}/workers — Step 3: worker assignments.

    Body:
        workers: [
            {
                "user_id": "worker-001",
                "channel_type": "line",
                "channel_id": "U12345abcdef"
            }
        ]
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    workers = body.get("workers")
    if not workers or not isinstance(workers, list):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'workers' must be a non-empty list of {user_id, channel_type, channel_id}."},
        )

    registered: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    try:
        db = client if client is not None else _get_supabase_client()

        for idx, w in enumerate(workers):
            if not isinstance(w, dict):
                errors.append({"index": idx, "error": "Item must be a JSON object."})
                continue

            user_id      = str(w.get("user_id") or "").strip()
            channel_type = str(w.get("channel_type") or "").lower().strip()
            channel_id   = str(w.get("channel_id") or "").strip()

            if not user_id:
                errors.append({"index": idx, "error": "Missing 'user_id'."})
                continue
            if not channel_type:
                errors.append({"index": idx, "error": "Missing 'channel_type'."})
                continue
            if channel_type not in _VALID_CHANNEL_TYPES:
                errors.append({
                    "index": idx,
                    "error": f"Unknown channel_type '{channel_type}'. "
                             f"Valid: {sorted(_VALID_CHANNEL_TYPES)}",
                })
                continue
            if not channel_id:
                errors.append({"index": idx, "error": "Missing 'channel_id'."})
                continue

            try:
                row_data = {
                    "tenant_id":    tenant_id,
                    "user_id":      user_id,
                    "channel_type": channel_type,
                    "channel_id":   channel_id,
                    "active":       True,
                }
                # Upsert on (tenant_id, user_id, channel_type)
                db.table("notification_channels").upsert(
                    row_data,
                    on_conflict="tenant_id,user_id,channel_type",
                ).execute()
                registered.append({
                    "user_id":      user_id,
                    "channel_type": channel_type,
                    "channel_id":   channel_id,
                })

            except Exception as row_exc:  # noqa: BLE001
                errors.append({
                    "index":    idx,
                    "user_id":  user_id,
                    "error":    str(row_exc)[:120],
                })

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /onboarding/%s/workers error tenant=%s: %s", property_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    return JSONResponse(
        status_code=200,
        content={
            "property_id": property_id,
            "registered":  registered,
            "errors":      errors,
            "next_step":   f"GET /onboarding/{property_id}/status",
        },
    )


# ---------------------------------------------------------------------------
# Status — GET /onboarding/{property_id}/status
# ---------------------------------------------------------------------------

@router.get(
    "/{property_id}/status",
    tags=["onboarding"],
    summary="Get onboarding completion status for a property (Phase 214)",
    description=(
        "Derives onboarding completion state across all three steps.\\n\\n"
        "Returns `steps_complete` (0–3) and per-step detail.\\n\\n"
        "Step 1 ✅ — property exists in `properties`.\\n"
        "Step 2 ✅ — at least one channel mapping in `channel_map`.\\n"
        "Step 3 ✅ — at least one worker in `notification_channels` for this tenant.\\n\\n"
        "Never returns 404 — returns zero completions if property is fresh/unknown."
    ),
    responses={
        200: {"description": "Onboarding status."},
        401: {"description": "Missing or invalid JWT token."},
        500: {"description": "Internal server error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def onboarding_status(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """GET /onboarding/{property_id}/status — overall onboarding health."""
    try:
        db = client if client is not None else _get_supabase_client()

        # Step 1: property exists?
        prop_res = (
            db.table("properties")
            .select("property_id, display_name, timezone, base_currency")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        step1_rows = prop_res.data or []
        step1_complete = len(step1_rows) > 0
        step1_detail = step1_rows[0] if step1_rows else {}

        # Step 2: channel_map entries?
        cm_res = (
            db.table("channel_map")
            .select("provider, external_channel_id")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .eq("active", True)
            .execute()
        )
        step2_rows = cm_res.data or []
        step2_complete = len(step2_rows) > 0

        # Step 3: notification_channels for this tenant (any worker)
        nc_res = (
            db.table("notification_channels")
            .select("user_id, channel_type, channel_id")
            .eq("tenant_id", tenant_id)
            .eq("active", True)
            .execute()
        )
        step3_rows = nc_res.data or []
        step3_complete = len(step3_rows) > 0

        steps_complete = sum([step1_complete, step2_complete, step3_complete])

        return JSONResponse(
            status_code=200,
            content={
                "property_id":    property_id,
                "steps_complete": steps_complete,
                "onboarding_done": steps_complete == 3,
                "steps": {
                    "step_1_property": {
                        "complete": step1_complete,
                        "detail":   step1_detail,
                    },
                    "step_2_channels": {
                        "complete": step2_complete,
                        "count":    len(step2_rows),
                        "channels": step2_rows,
                    },
                    "step_3_workers": {
                        "complete": step3_complete,
                        "count":    len(step3_rows),
                        "workers":  step3_rows,
                    },
                },
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "GET /onboarding/%s/status error tenant=%s: %s", property_id, tenant_id, exc
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
