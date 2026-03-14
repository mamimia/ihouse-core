"""
Phase 593 — Property Amenities API

Endpoints:
    POST /properties/{id}/amenities  — bulk upsert amenities
    GET  /properties/{id}/amenities  — list amenities (grouped by category)
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


_VALID_CATEGORIES = frozenset({
    "kitchen", "bathroom", "bedroom", "outdoor", "entertainment", "safety", "general",
})


@router.post(
    "/{property_id}/amenities",
    summary="Bulk upsert amenities for a property (Phase 593)",
    responses={200: {}, 400: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def upsert_amenities(
    property_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Request body must be a JSON object."})

    amenities = body.get("amenities")
    if not amenities or not isinstance(amenities, list):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'amenities' must be a non-empty list."})

    registered: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    try:
        db = client if client is not None else _get_supabase_client()

        for idx, a in enumerate(amenities):
            if not isinstance(a, dict):
                errors.append({"index": idx, "error": "Item must be a JSON object."})
                continue

            key = str(a.get("amenity_key") or "").strip().lower()
            cat = str(a.get("category") or "general").strip().lower()

            if not key:
                errors.append({"index": idx, "error": "Missing 'amenity_key'."})
                continue

            row = {
                "tenant_id": tenant_id, "property_id": property_id,
                "amenity_key": key, "category": cat,
                "available": a.get("available", True),
                "notes": a.get("notes"),
            }
            try:
                db.table("property_amenities").upsert(
                    row, on_conflict="tenant_id,property_id,amenity_key"
                ).execute()
                registered.append({"amenity_key": key, "category": cat})
            except Exception as row_exc:
                errors.append({"index": idx, "amenity_key": key, "error": str(row_exc)[:120]})

    except Exception as exc:
        logger.exception("upsert amenities error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)

    return JSONResponse(status_code=200, content={
        "property_id": property_id, "registered": registered,
        "errors": errors, "count": len(registered),
    })


@router.get(
    "/{property_id}/amenities",
    summary="List amenities for a property grouped by category (Phase 593)",
    responses={200: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def list_amenities(
    property_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("property_amenities").select("*")
            .eq("tenant_id", tenant_id).eq("property_id", property_id)
            .order("category", desc=False)
            .execute()
        )
        rows = result.data or []

        # Group by category
        grouped: Dict[str, List[Dict]] = {}
        for r in rows:
            cat = r.get("category", "general")
            grouped.setdefault(cat, []).append(r)

        return JSONResponse(status_code=200, content={
            "property_id": property_id, "count": len(rows),
            "by_category": grouped, "amenities": rows,
        })
    except Exception as exc:
        logger.exception("list amenities error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
