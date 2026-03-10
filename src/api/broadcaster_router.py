"""
Phase 173 — IPI: Proactive Availability Broadcasting API

Endpoint:
    POST /admin/broadcast/availability

Triggers a proactive availability broadcast for a property to all its
mapped OTA channels. Designed for two scenarios:

  1. PROPERTY_ONBOARDED — a property has just been configured with channel
     mappings and all its existing active bookings need to be synced outward.
  2. CHANNEL_ADDED — a new channel was added to an existing property and
     only bookings for that property need to be pushed to the new channel.

This endpoint is an orchestration trigger. It does NOT write to
booking_state or event_log. All actual sync work runs through the
existing Phase 137 + 138 trigger/executor pipeline.

Rules:
    - JWT required. Tenant-scoped.
    - Best-effort. Always returns 200 with a BroadcastReport.
    - One booking/channel failure does not abort others.
    - Dry-run safe: respects IHOUSE_DRY_RUN env var via adapter registry.
    - Never modifies canonical booking state.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_MODES = frozenset({"PROPERTY_ONBOARDED", "CHANNEL_ADDED"})


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


@router.post(
    "/admin/broadcast/availability",
    tags=["broadcast"],
    summary="Proactive IPI availability broadcast for a property (Phase 173)",
    description=(
        "Triggers a proactive availability broadcast for all active bookings "
        "of a property to all mapped OTA channels.\\n\\n"
        "**Mode `PROPERTY_ONBOARDED`:** pushes all active bookings to all mapped "
        "channels. Use when a property first gets channel mappings configured "
        "(fills availability gaps for existing bookings).\\n\\n"
        "**Mode `CHANNEL_ADDED`:** pushes all active bookings only to the newly "
        "added channel (`target_provider` required). Use when a single new channel "
        "is registered for an existing property.\\n\\n"
        "**Invariants:**\\n"
        "- Never modifies `booking_state` or `event_log`.\\n"
        "- Fully fail-isolated: one booking or channel failure does not abort others.\\n"
        "- All Phase 141-144 guarantees apply: throttle, retry, idempotency key, "
        "sync_log persistence.\\n"
        "- Always returns 200 with a full broadcast report."
    ),
    responses={
        200: {"description": "Broadcast complete. Report includes per-booking outcomes."},
        400: {"description": "Validation error — invalid mode or missing required field."},
        401: {"description": "Missing or invalid JWT."},
        500: {"description": "Internal error."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def broadcast_availability(
    body: dict,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    POST /admin/broadcast/availability

    Required body fields:
        property_id  : str   — property to broadcast for
        mode         : str   — PROPERTY_ONBOARDED | CHANNEL_ADDED

    Optional body fields:
        source_provider : str — OTA to exclude from targets (the booking source)
        target_provider : str — required when mode=CHANNEL_ADDED; only this
                                channel receives the broadcast
    """
    if not isinstance(body, dict):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "Request body must be a JSON object."},
        )

    property_id: Optional[str] = body.get("property_id")
    if not property_id or not isinstance(property_id, str):
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'property_id' is required and must be a string."},
        )

    mode: Optional[str] = body.get("mode")
    if not mode or mode not in _VALID_MODES:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={
                "detail": f"'mode' must be one of: {sorted(_VALID_MODES)}.",
                "provided": mode,
            },
        )

    source_provider: Optional[str] = body.get("source_provider") or None
    target_provider: Optional[str] = body.get("target_provider") or None

    if mode == "CHANNEL_ADDED" and not target_provider:
        return make_error_response(
            status_code=400,
            code=ErrorCode.VALIDATION_ERROR,
            extra={"detail": "'target_provider' is required when mode=CHANNEL_ADDED."},
        )

    try:
        from services.outbound_availability_broadcaster import (
            broadcast_availability as _broadcast,
            serialise_broadcast_report,
            BroadcastMode,
        )

        db = client if client is not None else _get_supabase_client()

        report = _broadcast(
            db,
            tenant_id=tenant_id,
            property_id=property_id,
            mode=mode,
            source_provider=source_provider,
            target_provider=target_provider,
        )

        return JSONResponse(
            status_code=200,
            content=serialise_broadcast_report(report),
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "POST /admin/broadcast/availability error: tenant=%s property=%s: %s",
            tenant_id, property_id, exc,
        )
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
