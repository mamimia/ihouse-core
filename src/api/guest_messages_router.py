"""
Phase 236 — Guest Communication History

Endpoints:
    POST /guest-messages/{booking_id}
        Log a sent (or received) guest message.
        Idempotent-safe: no unique constraint at DB level (each send is an
        independent event); duplicate POSTs simply insert additional rows.

        Body: {
            "direction":        "OUTBOUND" | "INBOUND",  (required)
            "channel":          "email" | "whatsapp" | "sms" | "line" | "telegram" | "manual",  (required)
            "intent":           "check_in_instructions" | …,  (optional)
            "content_preview":  "Dear Alex…",  (optional, truncated to 300)
            "draft_id":         "uuid",  (optional — link to Phase 227 draft)
            "sent_by":          "user-id",  (optional)
        }

    GET /guest-messages/{booking_id}
        Chronological timeline of all logged messages for this booking.
        Tenant-isolated; returns empty list if none.

Design:
    - No LLM dependency — pure CRUD
    - content_preview truncated to 300 chars server-side
    - JWT auth required; tenant isolation via .eq("tenant_id", …)
    - Phase 227 draft_id is optional — linking is caller-driven
    - No writes to booking_state, event_log, or tasks
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.auth import jwt_auth
from api.error_models import ErrorCode, make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_DIRECTIONS = {"OUTBOUND", "INBOUND"}
_VALID_CHANNELS = {"email", "whatsapp", "sms", "line", "telegram", "manual"}
_PREVIEW_LIMIT = 300


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_db() -> Any:
    from supabase import create_client  # type: ignore[import]
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ---------------------------------------------------------------------------
# POST /guest-messages/{booking_id}
# ---------------------------------------------------------------------------

@router.post(
    "/guest-messages/{booking_id}",
    tags=["guest-comms"],
    summary="Log a sent guest message (Phase 236)",
    responses={
        201: {"description": "Message logged"},
        400: {"description": "Invalid input"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Failed to persist"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def log_guest_message(
    booking_id: str,
    body: Optional[dict] = None,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Log a guest message that was actually sent (or received).

    **direction** — OUTBOUND (manager→guest) or INBOUND (guest→manager).
    **channel** — one of: email, whatsapp, sms, line, telegram, manual.
    **content_preview** — truncated to 300 characters server-side.
    **draft_id** — optionally links to a Phase 227 copilot draft.
    """
    if body is None:
        body = {}

    direction: Optional[str] = body.get("direction")
    channel: Optional[str] = body.get("channel")
    intent: Optional[str] = body.get("intent")
    content_preview: Optional[str] = body.get("content_preview")
    draft_id: Optional[str] = body.get("draft_id")
    sent_by: Optional[str] = body.get("sent_by")
    guest_id: Optional[str] = body.get("guest_id")

    # Validation
    if not direction or direction.upper() not in _VALID_DIRECTIONS:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            f"direction must be one of {sorted(_VALID_DIRECTIONS)}"
        )
    direction = direction.upper()

    if not channel or channel.lower() not in _VALID_CHANNELS:
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR,
            f"channel must be one of {sorted(_VALID_CHANNELS)}"
        )
    channel = channel.lower()

    if not booking_id or not booking_id.strip():
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "booking_id is required")

    # Truncate preview
    if content_preview and len(content_preview) > _PREVIEW_LIMIT:
        content_preview = content_preview[:_PREVIEW_LIMIT]

    try:
        db = client or _get_db()
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        row = {
            "tenant_id": tenant_id,
            "booking_id": booking_id,
            "guest_id": guest_id,
            "direction": direction,
            "channel": channel,
            "intent": intent,
            "content_preview": content_preview,
            "draft_id": draft_id,
            "sent_by": sent_by,
            "sent_at": now_iso,
            "created_at": now_iso,
        }

        result = db.table("guest_messages_log").insert(row).execute()
        record = (result.data or [{}])[0]

        return JSONResponse(
            status_code=201,
            content={
                "id": record.get("id"),
                "tenant_id": tenant_id,
                "booking_id": booking_id,
                "direction": direction,
                "channel": channel,
                "intent": intent,
                "content_preview": content_preview,
                "draft_id": draft_id,
                "sent_by": sent_by,
                "sent_at": now_iso,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("log_guest_message error tenant=%s booking=%s: %s", tenant_id, booking_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to log message")


# ---------------------------------------------------------------------------
# GET /guest-messages/{booking_id}
# ---------------------------------------------------------------------------

@router.get(
    "/guest-messages/{booking_id}",
    tags=["guest-comms"],
    summary="Guest communication timeline for a booking (Phase 236)",
    responses={
        200: {"description": "Chronological message timeline"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_guest_messages(
    booking_id: str,
    tenant_id: str = Depends(jwt_auth),
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Return all logged messages for a booking, oldest first.
    Returns empty list if no messages have been logged yet.
    """
    try:
        db = client or _get_db()

        result = (
            db.table("guest_messages_log")
            .select("id, direction, channel, intent, content_preview, draft_id, sent_by, sent_at, guest_id")
            .eq("tenant_id", tenant_id)
            .eq("booking_id", booking_id)
            .order("sent_at", desc=False)
            .execute()
        )
        messages = result.data or []

        return JSONResponse(
            status_code=200,
            content={
                "tenant_id": tenant_id,
                "booking_id": booking_id,
                "message_count": len(messages),
                "messages": messages,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("get_guest_messages error tenant=%s booking=%s: %s", tenant_id, booking_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to fetch messages")
