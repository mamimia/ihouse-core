"""
Phase 596 — Extras Catalog API

Endpoints:
    GET  /extras         — list all extras for this tenant
    POST /extras         — create a new extra
    GET  /extras/{id}    — get a single extra
    PATCH /extras/{id}   — update an extra
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
router = APIRouter(prefix="/extras", tags=["extras"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


_VALID_CATEGORIES = frozenset({
    "transport", "food", "wellness", "activities", "services", "other",
})


@router.get("/", summary="List extras catalog (Phase 596)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_extras(
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("extras_catalog").select("*")
            .eq("tenant_id", tenant_id).eq("active", True)
            .order("category", desc=False)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "count": len(rows), "extras": rows,
        })
    except Exception as exc:
        logger.exception("list extras error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post("/", summary="Create an extra (Phase 596)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def create_extra(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    name = str(body.get("name") or "").strip()
    if not name:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'name' is required."})

    category = str(body.get("category") or "other").strip().lower()
    row = {
        "tenant_id": tenant_id, "name": name,
        "description": body.get("description"),
        "icon": body.get("icon"),
        "default_price": body.get("default_price"),
        "currency": str(body.get("currency", "THB")).upper()[:3],
        "category": category,
        "is_system": body.get("is_system", False),
        "active": True,
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("extras_catalog").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("create extra error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/{extra_id}", summary="Get a single extra (Phase 596)",
            responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def get_extra(
    extra_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("extras_catalog").select("*")
            .eq("tenant_id", tenant_id).eq("id", extra_id)
            .limit(1).execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Extra '{extra_id}' not found."})
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("get extra error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.patch("/{extra_id}", summary="Update an extra (Phase 596)",
              responses={200: {}, 400: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def update_extra(
    extra_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict) or not body:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a non-empty JSON object."})

    allowed = {"name", "description", "icon", "default_price", "currency", "category", "active"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"No updatable fields. Allowed: {sorted(allowed)}"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("extras_catalog").update(update)
            .eq("tenant_id", tenant_id).eq("id", extra_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Extra '{extra_id}' not found."})
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("update extra error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
