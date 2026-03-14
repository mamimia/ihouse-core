"""
Phase 597 — Property-Extras Mapping API

Endpoints:
    POST   /properties/{id}/extras             — enable extras for property
    GET    /properties/{id}/extras             — list active extras for property
    PATCH  /properties/{id}/extras/{extra_id}  — override price, toggle
    DELETE /properties/{id}/extras/{extra_id}  — deactivate
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
router = APIRouter(prefix="/properties", tags=["properties", "extras"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


@router.post(
    "/{property_id}/extras",
    summary="Enable extras for a property (Phase 597)",
    responses={200: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def add_property_extras(
    property_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    extras = body.get("extras")
    if not extras or not isinstance(extras, list):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'extras' must be a non-empty list of {extra_id, price_override?}."})

    registered: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    try:
        db = client if client is not None else _get_supabase_client()
        for idx, e in enumerate(extras):
            if not isinstance(e, dict):
                errors.append({"index": idx, "error": "Must be an object."})
                continue
            extra_id = str(e.get("extra_id") or "").strip()
            if not extra_id:
                errors.append({"index": idx, "error": "Missing 'extra_id'."})
                continue
            row = {
                "tenant_id": tenant_id, "property_id": property_id,
                "extra_id": extra_id, "active": True,
                "price_override": e.get("price_override"),
                "notes": e.get("notes"),
            }
            try:
                db.table("property_extras").upsert(
                    row, on_conflict="tenant_id,property_id,extra_id"
                ).execute()
                registered.append({"extra_id": extra_id})
            except Exception as row_exc:
                errors.append({"index": idx, "extra_id": extra_id, "error": str(row_exc)[:120]})
    except Exception as exc:
        logger.exception("add property extras error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    return JSONResponse(status_code=200, content={
        "property_id": property_id, "registered": registered, "errors": errors,
    })


@router.get(
    "/{property_id}/extras",
    summary="List active extras for a property (Phase 597)",
    responses={200: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_property_extras(
    property_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("property_extras").select("*")
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .eq("active", True)
            .execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "count": len(rows), "extras": rows,
        })
    except Exception as exc:
        logger.exception("list property extras error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.patch(
    "/{property_id}/extras/{extra_id}",
    summary="Update property extra mapping (Phase 597)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def update_property_extra(
    property_id: str, extra_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict) or not body:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a non-empty JSON object."})
    allowed = {"price_override", "active", "notes"}
    update = {k: v for k, v in body.items() if k in allowed}
    if not update:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"No updatable fields. Allowed: {sorted(allowed)}"})
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("property_extras").update(update)
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .eq("extra_id", extra_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Property extra mapping not found."})
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("update property extra error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.delete(
    "/{property_id}/extras/{extra_id}",
    summary="Deactivate a property extra (Phase 597)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def deactivate_property_extra(
    property_id: str, extra_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("property_extras").update({"active": False})
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .eq("extra_id", extra_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": "Property extra mapping not found."})
        return JSONResponse(status_code=200, content={"deactivated": True, "extra_id": extra_id})
    except Exception as exc:
        logger.exception("deactivate property extra error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
