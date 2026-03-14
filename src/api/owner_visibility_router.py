"""
Phase 604 — Owner Visibility Settings API

Endpoints:
    GET /owner/visibility/{property_id}  — get visibility settings
    PUT /owner/visibility/{property_id}  — set visibility settings
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/owner", tags=["owner"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


_DEFAULT_VISIBILITY = {
    "booking_count": True, "occupancy_calendar": True, "guest_names": True,
    "price_per_night": False, "revenue": False, "cleaning_status": True,
    "maintenance_reports": True, "operational_costs": False,
    "guest_reviews": True, "worker_details": False,
}


@router.get(
    "/visibility/{property_id}",
    summary="Get owner visibility settings (Phase 604)",
    responses={200: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_visibility(
    property_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("owner_visibility_settings").select("*")
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .limit(1).execute()
        )
        rows = result.data or []
        if rows:
            return JSONResponse(status_code=200, content=rows[0])
        # Return defaults if not set
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "visible_fields": _DEFAULT_VISIBILITY,
            "is_default": True,
        })
    except Exception as exc:
        logger.exception("get visibility error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.put(
    "/visibility/{property_id}",
    summary="Set owner visibility settings (Phase 604)",
    responses={200: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def set_visibility(
    property_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    visible_fields = body.get("visible_fields")
    owner_user_id = str(body.get("owner_user_id") or tenant_id).strip()

    if visible_fields is None or not isinstance(visible_fields, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'visible_fields' must be a JSON object."})

    import json
    row = {
        "tenant_id": tenant_id, "owner_user_id": owner_user_id,
        "property_id": property_id,
        "visible_fields": json.dumps(visible_fields),
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("owner_visibility_settings").upsert(
            row, on_conflict="tenant_id,owner_user_id,property_id"
        ).execute()
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "owner_user_id": owner_user_id,
            "visible_fields": visible_fields, "saved": True,
        })
    except Exception as exc:
        logger.exception("set visibility error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
