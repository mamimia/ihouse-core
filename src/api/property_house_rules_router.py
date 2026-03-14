"""
Phase 589 — House Rules API

Endpoints:
    PUT  /properties/{id}/house-rules  — replace rules array
    GET  /properties/{id}/house-rules  — get rules
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


@router.put(
    "/{property_id}/house-rules",
    summary="Replace house rules for a property (Phase 589)",
    responses={200: {}, 400: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def set_house_rules(
    property_id: str,
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Request body must be a JSON object."})

    rules = body.get("rules")
    if rules is None or not isinstance(rules, list):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'rules' must be a list of rule objects."})

    try:
        db = client if client is not None else _get_supabase_client()
        import json
        result = (
            db.table("properties")
            .update({"house_rules": json.dumps(rules)})
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Property '{property_id}' not found."})
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "rules": rules, "count": len(rules),
        })
    except Exception as exc:
        logger.exception("set house-rules error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/{property_id}/house-rules",
    summary="Get house rules for a property (Phase 589)",
    responses={200: {}, 404: {}, 500: {}},
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_house_rules(
    property_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("properties")
            .select("property_id, house_rules")
            .eq("tenant_id", tenant_id)
            .eq("property_id", property_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Property '{property_id}' not found."})
        rules = rows[0].get("house_rules") or []
        return JSONResponse(status_code=200, content={
            "property_id": property_id, "rules": rules, "count": len(rules),
        })
    except Exception as exc:
        logger.exception("get house-rules error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
