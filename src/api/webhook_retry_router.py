"""
Phase 508 — Webhook Retry Management API Router

Exposes the webhook_retry.py service (Phase 500) via HTTP endpoints.

Endpoints:
    GET  /admin/webhook-retry/queue  — List pending retry queue items
    POST /admin/webhook-retry/process — Process pending retries (dry-run supported)
    GET  /admin/webhook-retry/dlq    — List items in webhook dead-letter queue
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter(tags=["webhook-retry"])


def _get_supabase_client() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


@router.get(
    "/admin/webhook-retry/queue",
    tags=["webhook-retry"],
    summary="List pending webhook retries (Phase 508)",
    responses={
        200: {"description": "Retry queue entries."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_retry_queue(
    limit: int = Query(default=50, ge=1, le=200, description="Max entries"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("webhook_retry_queue")
            .select("*")
            .order("next_attempt_at", desc=False)
            .limit(limit)
            .execute()
        )
        entries = result.data or []
        return JSONResponse(status_code=200, content={
            "total": len(entries),
            "entries": entries,
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/webhook-retry/queue error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.post(
    "/admin/webhook-retry/process",
    tags=["webhook-retry"],
    summary="Process pending webhook retries (Phase 508)",
    responses={
        200: {"description": "Processing result stats."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def process_retries(
    dry_run: bool = Query(default=True, description="If true, do not actually dispatch"),
    limit: int = Query(default=50, ge=1, le=200, description="Max entries to process"),
    tenant_id: str = Depends(jwt_auth),
) -> JSONResponse:
    try:
        from services.webhook_retry import process_retry_queue
        result = process_retry_queue(dry_run=dry_run, limit=limit)
        return JSONResponse(status_code=200, content=result)
    except Exception as exc:  # noqa: BLE001
        logger.exception("POST /admin/webhook-retry/process error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)


@router.get(
    "/admin/webhook-retry/dlq",
    tags=["webhook-retry"],
    summary="List webhook dead-letter queue entries (Phase 508)",
    responses={
        200: {"description": "DLQ entries."},
        401: {"description": "Missing or invalid JWT."},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_webhook_dlq(
    limit: int = Query(default=50, ge=1, le=200, description="Max entries"),
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    try:
        db = client if client is not None else _get_supabase_client()
        result = (
            db.table("webhook_dlq")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        entries = result.data or []
        return JSONResponse(status_code=200, content={
            "total": len(entries),
            "entries": entries,
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception("GET /admin/webhook-retry/dlq error: %s", exc)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
