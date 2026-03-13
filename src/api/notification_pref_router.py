"""
Phase 509 — Notification Preferences API Router

Exposes the notification_preferences.py service (Phase 503) via HTTP endpoints.

Endpoints:
    GET  /admin/notification-preferences/{user_id}  — Get user preferences
    PUT  /admin/notification-preferences/{user_id}  — Update user preferences
    GET  /admin/notification-preferences/types       — List available notification types
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification-preferences"])


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


class UpdatePreferencesRequest(BaseModel):
    enabled_types: Optional[List[str]] = Field(default=None, description="Notification types to enable")
    quiet_hours_start: Optional[str] = Field(default=None, description="Quiet hours start (HH:MM)")
    quiet_hours_end: Optional[str] = Field(default=None, description="Quiet hours end (HH:MM)")
    preferred_channel: Optional[str] = Field(default=None, description="Preferred channel (email/sms/whatsapp/line)")


@router.get(
    "/admin/notification-preferences/types",
    tags=["notification-preferences"],
    summary="List available notification types (Phase 509)",
    responses={200: {"description": "Notification types list."}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_notification_types(
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    from services.notification_preferences import NOTIFICATION_TYPES
    return JSONResponse(status_code=200, content={"types": NOTIFICATION_TYPES})


@router.get(
    "/admin/notification-preferences/{user_id}",
    tags=["notification-preferences"],
    summary="Get notification preferences for a user (Phase 509)",
    responses={
        200: {"description": "User preferences."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_notification_preferences(
    user_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        from services.notification_preferences import get_preferences

        db = client if client is not None else _get_supabase_client()
        result = get_preferences(db, tenant_id, user_id)
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/notification-preferences/%s error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.put(
    "/admin/notification-preferences/{user_id}",
    tags=["notification-preferences"],
    summary="Update notification preferences for a user (Phase 509)",
    responses={
        200: {"description": "Updated preferences."},
        400: {"description": "Invalid input."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_notification_preferences(
    user_id: str,
    body: UpdatePreferencesRequest,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        from services.notification_preferences import update_preferences

        db = client if client is not None else _get_supabase_client()
        result = update_preferences(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            enabled_types=body.enabled_types,
            quiet_hours_start=body.quiet_hours_start,
            quiet_hours_end=body.quiet_hours_end,
            preferred_channel=body.preferred_channel,
        )
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(status_code=200, content=result)

    except Exception as exc:  # noqa: BLE001
        logger.exception("PUT /admin/notification-preferences/%s error: %s", user_id, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
