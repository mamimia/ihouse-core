"""
Phases 591–592 — Property Reference & Marketing Photos API

Endpoints:
    POST   /properties/{id}/reference-photos   — upload reference photo
    GET    /properties/{id}/reference-photos    — list reference photos
    DELETE /properties/{id}/reference-photos/{photo_id}
    POST   /properties/{id}/marketing-photos   — upload marketing photo
    GET    /properties/{id}/marketing-photos    — list marketing photos
    DELETE /properties/{id}/marketing-photos/{photo_id}
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
router = APIRouter(prefix="/properties", tags=["properties"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ---------------------------------------------------------------------------
# Generic photo CRUD (reused for both tables)
# ---------------------------------------------------------------------------

async def _add_photo(
    table: str, property_id: str, body: Dict[str, Any],
    tenant_id: str, client: Optional[Any], extra_fields: Optional[Dict] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Request body must be a JSON object."})

    photo_url = str(body.get("photo_url") or "").strip()
    if not photo_url:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'photo_url' is required."})

    row: Dict[str, Any] = {
        "tenant_id": tenant_id, "property_id": property_id,
        "photo_url": photo_url, "display_order": body.get("display_order", 0),
    }
    if extra_fields:
        row.update(extra_fields)

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table(table).insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("add photo to %s error: %s", table, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


async def _list_photos(
    table: str, property_id: str, tenant_id: str, client: Optional[Any],
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table(table).select("*")
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .order("display_order", desc=False)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "count": len(rows), "photos": rows,
        })
    except Exception as exc:
        logger.exception("list photos from %s error: %s", table, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


async def _delete_photo(
    table: str, property_id: str, photo_id: str,
    tenant_id: str, client: Optional[Any],
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table(table).delete()
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .eq("id", photo_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Photo '{photo_id}' not found."})
        return JSONResponse(status_code=200, content={"deleted": True, "photo_id": photo_id})
    except Exception as exc:
        logger.exception("delete photo from %s error: %s", table, exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


# ---------------------------------------------------------------------------
# Phase 591 — Reference Photos
# ---------------------------------------------------------------------------

@router.post("/{property_id}/reference-photos", summary="Upload reference photo (Phase 591)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def add_reference_photo(property_id: str, body: Dict[str, Any],
                              tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None) -> JSONResponse:
    room_label = str(body.get("room_label", "")).strip() if isinstance(body, dict) else ""
    if not room_label:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'room_label' is required."})
    return await _add_photo("property_reference_photos", property_id, body, tenant_id, client,
                             extra_fields={"room_label": room_label})


@router.get("/{property_id}/reference-photos", summary="List reference photos (Phase 591)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_reference_photos(property_id: str, tenant_id: str = Depends(jwt_auth),
                                client: Optional[Any] = None) -> JSONResponse:
    return await _list_photos("property_reference_photos", property_id, tenant_id, client)


@router.delete("/{property_id}/reference-photos/{photo_id}", summary="Delete reference photo (Phase 591)",
               responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def delete_reference_photo(property_id: str, photo_id: str, tenant_id: str = Depends(jwt_auth),
                                 client: Optional[Any] = None) -> JSONResponse:
    return await _delete_photo("property_reference_photos", property_id, photo_id, tenant_id, client)


# ---------------------------------------------------------------------------
# Phase 592 — Marketing Photos
# ---------------------------------------------------------------------------

@router.post("/{property_id}/marketing-photos", summary="Upload marketing photo (Phase 592)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def add_marketing_photo(property_id: str, body: Dict[str, Any],
                              tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None) -> JSONResponse:
    caption = body.get("caption") if isinstance(body, dict) else None
    source = str(body.get("source", "upload")).strip() if isinstance(body, dict) else "upload"
    return await _add_photo("property_marketing_photos", property_id, body, tenant_id, client,
                             extra_fields={"caption": caption, "source": source})


@router.get("/{property_id}/marketing-photos", summary="List marketing photos (Phase 592)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_marketing_photos(property_id: str, tenant_id: str = Depends(jwt_auth),
                                client: Optional[Any] = None) -> JSONResponse:
    return await _list_photos("property_marketing_photos", property_id, tenant_id, client)


@router.delete("/{property_id}/marketing-photos/{photo_id}", summary="Delete marketing photo (Phase 592)",
               responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def delete_marketing_photo(property_id: str, photo_id: str, tenant_id: str = Depends(jwt_auth),
                                 client: Optional[Any] = None) -> JSONResponse:
    return await _delete_photo("property_marketing_photos", property_id, photo_id, tenant_id, client)
