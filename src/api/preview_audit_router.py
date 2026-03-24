"""
Phase 867 — Preview Audit Router
==================================

Dedicated endpoint for recording preview session open/close events
to the structured audit_events table.

POST /admin/preview/audit

This endpoint is EXEMPT from the PreviewModeMiddleware blocking
because it must be callable during an active preview session.

Audit event shape:
    entity_type = "preview"
    entity_id   = "preview_session"
    action      = "PREVIEW_OPENED" | "PREVIEW_CLOSED"
    payload     = {
        "preview_role": "cleaner",  # the role being previewed
        "route": "/ops/cleaner",     # the target route
    }
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.auth import jwt_identity

logger = logging.getLogger(__name__)

router = APIRouter()


class PreviewAuditRequest(BaseModel):
    action: str = Field(..., pattern="^PREVIEW_(OPENED|CLOSED)$")
    preview_role: str = Field(..., min_length=1, max_length=50)
    route: Optional[str] = Field(default=None, max_length=200)


@router.post(
    "/admin/preview/audit",
    tags=["audit"],
    summary="Record preview open/close audit event (Phase 867)",
    responses={
        200: {"description": "Audit event recorded"},
        403: {"description": "Not an admin user"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def record_preview_audit(
    body: PreviewAuditRequest,
    identity: dict = Depends(jwt_identity),
) -> JSONResponse:
    """
    Record a structured preview audit event.

    Only admin users can record preview events.
    """
    # The jwt_identity dep may have already overridden role to preview_role,
    # but we need to verify admin context. Check is_preview flag or original role.
    # In preview mode, identity has is_preview=True (set by auth.py Phase 866).
    # If not in preview, the user must be admin directly.
    is_admin = (
        identity.get("is_preview") is True  # admin in preview mode
        or identity.get("role") == "admin"   # admin not in preview
    )

    if not is_admin:
        return JSONResponse(
            status_code=403,
            content={
                "ok": False,
                "error": {"message": "Admin only", "code": "ADMIN_REQUIRED"},
            },
        )

    tenant_id = identity.get("tenant_id", "")
    user_id = identity.get("user_id", "")

    # Write structured audit event (best-effort, never fails the request)
    try:
        from services.audit_writer import write_audit_event
        write_audit_event(
            tenant_id=tenant_id,
            actor_id=user_id,
            action=body.action,
            entity_type="preview",
            entity_id="preview_session",
            payload={
                "preview_role": body.preview_role,
                "route": body.route or "",
            },
        )
        logger.info(
            "Preview audit: %s by user=%s role=%s route=%s",
            body.action,
            user_id,
            body.preview_role,
            body.route,
        )
    except Exception as exc:
        logger.warning("Preview audit write failed (best-effort): %s", exc)

    return JSONResponse(
        status_code=200,
        content={"ok": True, "data": {"recorded": True, "action": body.action}},
    )
