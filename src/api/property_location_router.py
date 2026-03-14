"""
Phase 586 — Property GPS & Location API

Endpoints:
    POST /properties/{id}/save-location  — save device GPS coordinates
    GET  /properties/{id}/location       — get coordinates + map link
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
router = APIRouter(prefix="/properties", tags=["properties"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


@router.post(
    "/{property_id}/save-location",
    summary="Save GPS coordinates for a property (Phase 586)",
    responses={200: {}, 400: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def save_location(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Request body must be a JSON object."})

    lat = body.get("latitude")
    lng = body.get("longitude")
    source = str(body.get("source", "manual")).strip()

    if lat is None or lng is None:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'latitude' and 'longitude' are required."})
    try:
        lat = float(lat)
        lng = float(lng)
    except (ValueError, TypeError):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "latitude/longitude must be numeric."})

    if not (-90 <= lat <= 90):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"latitude must be -90 to 90. Got: {lat}"})
    if not (-180 <= lng <= 180):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"longitude must be -180 to 180. Got: {lng}"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .update({"latitude": lat, "longitude": lng, "gps_source": source, "gps_saved_at": "now()"})
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Property '{property_id}' not found."})
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "latitude": lat, "longitude": lng,
            "gps_source": source, "saved": True,
        })
    except Exception as exc:
        logger.exception("save-location error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/{property_id}/location",
    summary="Get GPS location for a property (Phase 586)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_location(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .select("property_id, latitude, longitude, gps_source, gps_saved_at")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Property '{property_id}' not found."})
        row = rows[0]
        lat = row.get("latitude")
        lng = row.get("longitude")
        map_url = f"https://maps.google.com/?q={lat},{lng}" if lat is not None and lng is not None else None
        return JSONResponse(status_code=200, content={
            "property_id": property_id,
            "latitude": lat, "longitude": lng,
            "gps_source": row.get("gps_source"),
            "gps_saved_at": row.get("gps_saved_at"),
            "map_url": map_url,
        })
    except Exception as exc:
        logger.exception("get-location error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
