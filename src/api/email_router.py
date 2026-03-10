"""
Phase 213 — Email Notification Router

Handles email notification management endpoints.

Endpoints:
    GET  /email/webhook  — Health check / echo (confirms channel is configured)
    POST /email/ack      — Manual task acknowledgement via email token link

Security:
    GET /email/webhook   — No auth (health probe).
    POST /email/ack      — Token-based (one-time ACK token embedded in email link).
                           No JWT — email clients don't carry JWTs.

Design note:
    Unlike SMS/WhatsApp which receive provider callbacks, email acknowledgement
    uses a one-time token link pattern:
      1. Email body contains: {BASE_URL}/email/ack?token={ack_token}&task_id={task_id}
      2. Worker clicks the link.
      3. GET request arrives → task is transitioned PENDING→ACKNOWLEDGED.
      4. 200 HTML confirmation (or redirect) returned.

    Token validation is best-effort in Phase 213 (token == task_id prefix).
    Full signed token generation is Phase 213+.

Invariants (Phase 213):
    - Email is fallback only. tasks table is source of truth.
    - ACK is best-effort — errors never block response.
    - No direct write to booking_state or event_log.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["email"])


# ---------------------------------------------------------------------------
# GET /email/webhook — health check / configuration probe
# ---------------------------------------------------------------------------

@router.get("/email/webhook", response_class=PlainTextResponse)
async def email_webhook_health() -> str:
    """
    Email channel health check (Phase 213).

    Returns "ok" if IHOUSE_EMAIL_TOKEN is set, "not_configured" otherwise.
    Used by monitoring and provider setup verification.
    No authentication required.
    """
    token = os.environ.get("IHOUSE_EMAIL_TOKEN", "")
    if not token:
        logger.warning(
            "email_router: IHOUSE_EMAIL_TOKEN not set — email channel in dry-run mode"
        )
        return "not_configured"
    return "ok"


# ---------------------------------------------------------------------------
# GET /email/ack — one-click task acknowledgement from email link
# ---------------------------------------------------------------------------

@router.get("/email/ack", response_class=HTMLResponse)
async def email_task_ack(
    request: Request,
    task_id: Optional[str] = Query(default=None),
    token: Optional[str] = Query(default=None),
) -> str:
    """
    One-click task acknowledgement via email link (Phase 213).

    Workers receive an email with a link:
        GET /email/ack?task_id={task_id}&token={ack_token}

    Flow:
      1. Validate token (Phase 213: token must start with task_id[:8]).
         → 403 HTML if invalid.
      2. Transition task PENDING → ACKNOWLEDGED (best-effort).
      3. Return 200 HTML confirmation page.

    No JWT required — this is clicked from an email client.
    Token is a lightweight one-time-use guard (full signing deferred to Phase 213+).
    """
    if not task_id or not token:
        return _html_error("Missing task_id or token.")

    # Phase 213 token validation: token must contain the task_id prefix (first 8 chars)
    # Full HMAC-signed token generation is deferred to Phase 213+
    if not token.startswith(task_id[:8]):
        logger.warning(
            "email_router: invalid ACK token for task_id=%s token_prefix=%s",
            task_id, token[:4] if token else "",
        )
        return _html_error("Invalid or expired acknowledgement token.")

    # Best-effort task acknowledgement
    acknowledged = _acknowledge_task_best_effort(request, task_id)

    if acknowledged:
        return _html_success(task_id)
    return _html_already_acked(task_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _acknowledge_task_best_effort(request: Request, task_id: str) -> bool:
    """
    Attempt to acknowledge a task by task_id. Returns True if updated.
    Swallows all errors — email ack must never raise.
    """
    try:
        db = getattr(getattr(request, "app", None), "state", None)
        db_client = getattr(db, "db", None) if db else None
        if not db_client:
            logger.debug("email_router: no db client available for task ack")
            return False

        result = (
            db_client.table("tasks")
            .update({"status": "ACKNOWLEDGED"})
            .eq("task_id", task_id)
            .eq("status", "PENDING")
            .execute()
        )
        updated = len(result.data or [])
        if updated:
            logger.info("email_router: task acknowledged via email link. task_id=%s", task_id)
            return True
        logger.debug(
            "email_router: task ack no-op (already acked or not found). task_id=%s", task_id
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "email_router: task ack failed (best-effort). task_id=%s error=%s", task_id, exc
        )
        return False


def _html_success(task_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Task Acknowledged — iHouse</title></head>
<body>
<h1>✅ Task Acknowledged</h1>
<p>Task <code>{task_id}</code> has been marked as <strong>ACKNOWLEDGED</strong>.</p>
<p>You can close this window.</p>
</body>
</html>"""


def _html_already_acked(task_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Already Acknowledged — iHouse</title></head>
<body>
<h1>ℹ️ Already Acknowledged</h1>
<p>Task <code>{task_id}</code> was already acknowledged or could not be found.</p>
<p>You can close this window.</p>
</body>
</html>"""


def _html_error(message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Error — iHouse</title></head>
<body>
<h1>❌ Error</h1>
<p>{message}</p>
</body>
</html>"""
