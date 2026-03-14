"""
Phase 598 — Problem Reports API

Endpoints:
    POST  /problem-reports                   — create a problem report
    GET   /problem-reports                   — list reports (filters: property_id, status, priority)
    GET   /problem-reports/{id}              — get single report
    PATCH /problem-reports/{id}              — update status, assign, resolve
    POST  /problem-reports/{id}/photos       — add photo to report
    GET   /problem-reports/{id}/photos       — list photos for report
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/problem-reports", tags=["problem-reports"])


def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


_VALID_CATEGORIES = frozenset({
    "pool", "plumbing", "electrical", "ac_heating", "furniture",
    "structure", "tv_electronics", "bathroom", "kitchen",
    "garden_outdoor", "pest", "cleanliness", "security", "other",
})

_VALID_STATUSES = frozenset({"open", "in_progress", "resolved", "dismissed"})
_VALID_PRIORITIES = frozenset({"urgent", "normal"})


@router.post("/", summary="Create a problem report (Phase 598)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def create_problem_report(
    body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})

    property_id = str(body.get("property_id") or "").strip()
    reported_by = str(body.get("reported_by") or "").strip()
    category = str(body.get("category") or "").strip().lower()
    description = str(body.get("description") or "").strip()

    if not property_id:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'property_id' is required."})
    if not reported_by:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'reported_by' (worker_id) is required."})
    if not category or category not in _VALID_CATEGORIES:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"'category' must be one of: {sorted(_VALID_CATEGORIES)}"})
    if not description:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'description' is required."})

    priority = str(body.get("priority", "normal")).strip().lower()
    if priority not in _VALID_PRIORITIES:
        priority = "normal"

    row = {
        "tenant_id": tenant_id, "property_id": property_id,
        "booking_id": body.get("booking_id"),
        "reported_by": reported_by, "category": category,
        "description": description,
        "description_original_lang": body.get("description_original_lang"),
        "priority": priority, "status": "open",
    }

    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("problem_reports").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("create problem report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/", summary="List problem reports (Phase 598)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_problem_reports(
    property_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        q = db.table("problem_reports").select("*").eq("tenant_id", tenant_id)
        if property_id:
            q = q.eq("property_id", property_id)
        if status:
            q = q.eq("status", status.lower())
        if priority:
            q = q.eq("priority", priority.lower())
        result = q.order("created_at", desc=True).execute()
        rows = result.data or []
        return JSONResponse(status_code=200, content={"count": len(rows), "reports": rows})
    except Exception as exc:
        logger.exception("list problem reports error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/{report_id}", summary="Get a problem report (Phase 598)",
            responses={200: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def get_problem_report(
    report_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("problem_reports").select("*")
            .eq("tenant_id", tenant_id).eq("id", report_id)
            .limit(1).execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Report '{report_id}' not found."})
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("get problem report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.patch("/{report_id}", summary="Update a problem report (Phase 598)",
              responses={200: {}, 400: {}, 404: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def update_problem_report(
    report_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict) or not body:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a non-empty JSON object."})

    allowed = {"status", "priority", "resolved_by", "resolution_notes", "description_translated", "maintenance_task_id"}
    update: Dict[str, Any] = {k: v for k, v in body.items() if k in allowed}

    if "status" in update:
        s = str(update["status"]).lower()
        if s not in _VALID_STATUSES:
            return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                       extra={"detail": f"Invalid status. Must be one of: {sorted(_VALID_STATUSES)}"})
        update["status"] = s
        if s == "resolved":
            import datetime
            update["resolved_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not update:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": f"No updatable fields. Allowed: {sorted(allowed)}"})

    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("problem_reports").update(update)
            .eq("tenant_id", tenant_id).eq("id", report_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=404, code="NOT_FOUND",
                                       extra={"detail": f"Report '{report_id}' not found."})
        return JSONResponse(status_code=200, content=rows[0])
    except Exception as exc:
        logger.exception("update problem report error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post("/{report_id}/photos", summary="Add photo to problem report (Phase 598)",
             responses={201: {}, 400: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def add_report_photo(
    report_id: str, body: Dict[str, Any],
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    if not isinstance(body, dict):
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "Body must be a JSON object."})
    photo_url = str(body.get("photo_url") or "").strip()
    if not photo_url:
        return make_error_response(status_code=400, code=ErrorCode.VALIDATION_ERROR,
                                   extra={"detail": "'photo_url' is required."})
    row = {"report_id": report_id, "photo_url": photo_url, "caption": body.get("caption")}
    try:
        db = client if client is not None else _get_supabase_client()
        result = db.table("problem_report_photos").insert(row).execute()
        rows = result.data or []
        if not rows:
            return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
        return JSONResponse(status_code=201, content=rows[0])
    except Exception as exc:
        logger.exception("add report photo error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get("/{report_id}/photos", summary="List photos for a problem report (Phase 598)",
            responses={200: {}, 500: {}}, openapi_extra={"security": [{"BearerAuth": []}]})
async def list_report_photos(
    report_id: str,
    tenant_id: str = Depends(jwt_auth), client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("problem_report_photos").select("*")
            .eq("report_id", report_id)
            .order("created_at", desc=False).execute()
        )
        rows = result.data or []
        return JSONResponse(status_code=200, content={"report_id": report_id, "count": len(rows), "photos": rows})
    except Exception as exc:
        logger.exception("list report photos error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
