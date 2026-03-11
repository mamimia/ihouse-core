"""
Phase 230 — AI Audit Log Admin Router

Provides a paginated admin endpoint to query the ai_audit_log table.

Endpoint:
    GET /admin/ai-audit-log
        Query params:
          - endpoint       (optional, partial match)
          - request_type   (optional, exact match)
          - generated_by   (optional: 'llm' | 'heuristic')
          - from_date      (optional, ISO date YYYY-MM-DD)
          - to_date        (optional, ISO date YYYY-MM-DD)
          - limit          (1-100, default 50)
          - offset         (default 0)
        Returns:
          {
            "tenant_id": "...",
            "total_returned": N,
            "limit": 50,
            "offset": 0,
            "filters_applied": {...},
            "entries": [ { log row }, ... ]
          }

Zero-risk: read-only. JWT required. Tenant-scoped.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import make_error_response

logger = logging.getLogger(__name__)

router = APIRouter()

_MIN_LIMIT = 1
_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


def _fetch_ai_audit_log(
    db: Any,
    tenant_id: str,
    endpoint: Optional[str],
    request_type: Optional[str],
    generated_by: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int,
    offset: int,
) -> list[dict]:
    """Fetch paginated rows from ai_audit_log. Returns empty list on error."""
    try:
        q = (
            db.table("ai_audit_log")
            .select("*")
            .eq("tenant_id", tenant_id)
        )
        if request_type:
            q = q.eq("request_type", request_type)
        if generated_by in ("llm", "heuristic"):
            q = q.eq("generated_by", generated_by)
        if from_date:
            q = q.gte("created_at", f"{from_date}T00:00:00Z")
        if to_date:
            q = q.lte("created_at", f"{to_date}T23:59:59Z")
        if endpoint:
            # ilike for partial match on endpoint path
            q = q.ilike("endpoint", f"%{endpoint}%")
        q = (
            q.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )
        result = q.execute()
        return result.data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("_fetch_ai_audit_log: %s", exc)
        return []


@router.get(
    "/admin/ai-audit-log",
    tags=["admin"],
    summary="AI Audit Log — paginated admin query (Phase 230)",
    description=(
        "Returns a paginated list of AI copilot interactions logged by the system.\\n\\n"
        "**Filters:** `endpoint` (partial), `request_type` (exact), `generated_by` "
        "('llm'|'heuristic'), `from_date` / `to_date` (YYYY-MM-DD).\\n\\n"
        "**Pagination:** `limit` (1–100, default 50), `offset` (default 0).\\n\\n"
        "**Zero-risk:** Read-only. JWT required. Tenant-scoped."
    ),
    responses={
        200: {"description": "AI audit log entries"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_ai_audit_log(
    endpoint: Optional[str] = Query(default=None, description="Filter by endpoint path (partial match)"),
    request_type: Optional[str] = Query(default=None, description="Filter by request type slug (exact)"),
    generated_by: Optional[str] = Query(default=None, description="Filter: 'llm' or 'heuristic'"),
    from_date: Optional[str] = Query(default=None, description="Start date YYYY-MM-DD (inclusive)"),
    to_date: Optional[str] = Query(default=None, description="End date YYYY-MM-DD (inclusive)"),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=_MIN_LIMIT, le=_MAX_LIMIT, description="Max rows (1–100)"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_db()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ai_audit_log_router: DB connection failed: %s", exc)
        return make_error_response(500, "INTERNAL_ERROR", "DB unavailable")

    entries = _fetch_ai_audit_log(
        db=db,
        tenant_id=tenant_id,
        endpoint=endpoint,
        request_type=request_type,
        generated_by=generated_by,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )

    filters_applied: dict[str, Any] = {}
    if endpoint:
        filters_applied["endpoint"] = endpoint
    if request_type:
        filters_applied["request_type"] = request_type
    if generated_by:
        filters_applied["generated_by"] = generated_by
    if from_date:
        filters_applied["from_date"] = from_date
    if to_date:
        filters_applied["to_date"] = to_date

    return JSONResponse(
        status_code=200,
        content={
            "tenant_id": tenant_id,
            "total_returned": len(entries),
            "limit": limit,
            "offset": offset,
            "filters_applied": filters_applied,
            "entries": entries,
        },
    )
