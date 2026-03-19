"""
Phase 124 — LINE Webhook Router

Receives LINE callback when a worker acknowledges a task via LINE.
Writes ACKNOWLEDGED status to the tasks table.

Endpoint:
    POST /line/webhook
    Body: { "task_id": str, "acked_by": str (optional) }

Rules:
    - Signature validation via LINE_WEBHOOK_SECRET (env).
      If LINE_WEBHOOK_SECRET is unset → dev mode: skip validation.
    - Writes ONLY to `tasks` table. Never writes to booking_state,
      event_log, or booking_financial_facts.
    - If task is already ACKNOWLEDGED → idempotent 200 (no error).
    - If task is PENDING → transitions to ACKNOWLEDGED.
    - If task is in terminal state (COMPLETED/CANCELED) → 409 CONFLICT.
    - Task not found → 404 NOT_FOUND.
    - Tenant isolation: task_id lookup is NOT tenant-scoped here
      (LINE has no tenant concept). Lookup by task_id only.
      This is acceptable because task_id is opaque/deterministic.

Invariant (Phase 124):
    This router NEVER reads from booking_financial_facts or booking_state.
    This router writes ONLY to the `tasks` table.
    LINE is fallback only — iHouse Core tasks table is the source of truth.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.error_models import ErrorCode, make_error_response
from tasks.task_model import TaskStatus, VALID_TASK_TRANSITIONS

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TERMINAL_STATUSES = {TaskStatus.COMPLETED.value, TaskStatus.CANCELED.value}


# ---------------------------------------------------------------------------
# Supabase client factory (patchable in tests)
# ---------------------------------------------------------------------------

def _get_supabase_client() -> Any:
    """Return a Supabase client. Patched in tests."""
    from supabase import create_client  # type: ignore[import]
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Signature validation
# ---------------------------------------------------------------------------

def _validate_line_signature(body: bytes, signature_header: str) -> bool:
    """
    Validate LINE webhook signature using HMAC-SHA256.

    In dev mode (LINE_WEBHOOK_SECRET unset) → always returns True.
    In production (LINE_WEBHOOK_SECRET set) → validates
    X-Line-Signature header against HMAC-SHA256(secret, body).
    """
    import base64
    secret = os.environ.get("LINE_WEBHOOK_SECRET", "")
    if not secret:
        # Dev mode: no validation
        return True
    mac = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    )
    expected_b64 = base64.b64encode(mac.digest()).decode("utf-8")
    return hmac.compare_digest(expected_b64, signature_header)


# ---------------------------------------------------------------------------
# POST /line/webhook
# ---------------------------------------------------------------------------

@router.post(
    "/line/webhook",
    tags=["line"],
    summary="Receive LINE task acknowledgement callback",
    responses={
        200: {"description": "Task acknowledged or already acknowledged"},
        400: {"description": "Missing or invalid request body"},
        401: {"description": "Invalid LINE webhook signature"},
        404: {"description": "Task not found"},
        409: {"description": "Task is in a terminal state (COMPLETED or CANCELED)"},
        500: {"description": "Unexpected internal error"},
    },
)
async def line_webhook(
    request: Request,
    client: Optional[Any] = None,
) -> JSONResponse:
    """
    Receive a LINE callback when a worker acknowledges a task via LINE.

    **Body:**
    ```json
    {
      "task_id": "abc123",
      "acked_by": "worker-name-optional"
    }
    ```

    **Signature validation:**
    - Production: validates `X-Line-Signature` header against HMAC-SHA256.
    - Dev mode (LINE_WEBHOOK_SECRET unset): signature check is skipped.

    **Idempotent:** If task is already ACKNOWLEDGED → returns 200 immediately.
    **Terminal tasks:** Returns 409 CONFLICT.

    **Source of truth:** This endpoint writes ONLY to `tasks`.
    LINE is NEVER the source of truth.
    """
    # --- Read body ---
    try:
        body_bytes = await request.body()
        body = await request.json()
    except Exception:
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "Invalid JSON body")

    # --- Signature validation ---
    sig_header = request.headers.get("X-Line-Signature", "")
    if not _validate_line_signature(body_bytes, sig_header):
        return make_error_response(401, ErrorCode.AUTH_FAILED, "Invalid LINE webhook signature")

    # --- Validate body fields ---
    if not isinstance(body, dict):
        return make_error_response(400, ErrorCode.VALIDATION_ERROR, "Body must be a JSON object")

    # --- Catch standard LINE Messaging API events for User ID discovery ---
    if "events" in body and isinstance(body["events"], list):
        for ev in body["events"]:
            source = ev.get("source", {})
            user_id = source.get("userId")
            if user_id:
                logger.info("=== LINE USER ID IDENTIFIED: %s ===", user_id)
                # In the future, this is where SMS deep-link verification maps the user_id to a tenant worker
        return JSONResponse(status_code=200, content={"status": "ok"})

    task_id = body.get("task_id")
    if not task_id or not isinstance(task_id, str):
        return make_error_response(
            400, ErrorCode.VALIDATION_ERROR, "'task_id' is required and must be a string"
        )

    acked_by: str = str(body.get("acked_by") or "LINE")

    try:
        db = client or _get_supabase_client()

        # --- Fetch task ---
        result = (
            db.table("tasks")
            .select("*")
            .eq("task_id", task_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            return make_error_response(404, ErrorCode.NOT_FOUND, f"Task '{task_id}' not found")

        row = result.data[0]
        current_status = row["status"]

        # --- Already acknowledged → idempotent 200 ---
        if current_status == TaskStatus.ACKNOWLEDGED.value:
            return JSONResponse(
                status_code=200,
                content={
                    "task_id": task_id,
                    "status": current_status,
                    "message": "Already acknowledged",
                    "acked_by": acked_by,
                },
            )

        # --- Terminal state → 409 ---
        if current_status in _TERMINAL_STATUSES:
            return make_error_response(
                409,
                ErrorCode.INVALID_TRANSITION,
                f"Task '{task_id}' is in terminal state {current_status} — cannot acknowledge",
            )

        # --- Validate PENDING → ACKNOWLEDGED ---
        if current_status != TaskStatus.PENDING.value:
            return make_error_response(
                409,
                ErrorCode.INVALID_TRANSITION,
                f"Task '{task_id}' is in state {current_status} — "
                f"only PENDING tasks can be acknowledged via LINE",
            )

        # --- Apply update ---
        now = datetime.now(tz=timezone.utc).isoformat()
        update_result = (
            db.table("tasks")
            .update({"status": TaskStatus.ACKNOWLEDGED.value, "updated_at": now})
            .eq("task_id", task_id)
            .execute()
        )
        updated_row = update_result.data[0] if update_result.data else {
            **row,
            "status": TaskStatus.ACKNOWLEDGED.value,
            "updated_at": now,
        }

        return JSONResponse(
            status_code=200,
            content={
                "task_id": task_id,
                "status": updated_row["status"],
                "message": "Task acknowledged via LINE",
                "acked_by": acked_by,
            },
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("line_webhook error for task_id=%s: %s", task_id, exc)
        return make_error_response(500, ErrorCode.INTERNAL_ERROR, "Failed to process LINE webhook")
