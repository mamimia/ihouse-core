"""
Phase 196 — WhatsApp Webhook Router

Handles inbound WhatsApp Cloud API callbacks (Meta) for task acknowledgement
and the Meta webhook challenge verification endpoint.

Endpoints:
    GET  /whatsapp/webhook  — Meta webhook challenge verification (hub.challenge)
    POST /whatsapp/webhook  — Inbound WhatsApp message → task PENDING→ACKNOWLEDGED

Security:
    POST endpoint does NOT use JWT (disabled — Meta does not send JWT).
    Instead, HMAC-SHA256 signature via X-Hub-Signature-256 is verified
    using IHOUSE_WHATSAPP_APP_SECRET env var.
    Invalid sig → 403. Missing sig → 403.

Invariants (Phase 196):
    - WhatsApp webhook is fallback only. tasks table is source of truth.
    - 200 is always returned to Meta after sig check (Meta requires fast 200).
    - Task state transition respects existing state machine invariants.
    - No direct write to booking_state or event_log.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse

from channels.whatsapp_escalation import verify_whatsapp_signature

logger = logging.getLogger(__name__)

router = APIRouter(tags=["whatsapp"])


# ---------------------------------------------------------------------------
# GET /whatsapp/webhook — Meta challenge verification
# ---------------------------------------------------------------------------

@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
async def whatsapp_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
) -> str:
    """
    Meta webhook verification challenge endpoint.

    Meta sends a GET with hub.mode="subscribe", hub.verify_token, and
    hub.challenge. We validate the verify_token and echo back hub.challenge.

    Returns:
        hub.challenge plaintext if verify_token matches.
        403 if verify_token does not match or is missing.
    """
    expected_token = os.environ.get("IHOUSE_WHATSAPP_VERIFY_TOKEN", "")
    if not expected_token:
        logger.warning("whatsapp_router: IHOUSE_WHATSAPP_VERIFY_TOKEN not set")
        raise HTTPException(status_code=403, detail="webhook_not_configured")

    if hub_mode != "subscribe" or hub_verify_token != expected_token:
        raise HTTPException(status_code=403, detail="invalid_verify_token")

    return hub_challenge or ""


# ---------------------------------------------------------------------------
# POST /whatsapp/webhook — Inbound message → task acknowledgement
# ---------------------------------------------------------------------------

@router.post("/whatsapp/webhook", status_code=200)
async def whatsapp_webhook_inbound(request: Request) -> dict:
    """
    Inbound WhatsApp Cloud API webhook.

    Flow:
      1. Verify X-Hub-Signature-256 (HMAC-SHA256 using app secret).
         → 403 if signature invalid or missing.
      2. Parse body for message text containing task_id.
      3. If valid task_id found → transition task PENDING→ACKNOWLEDGED.
      4. Return 200 always after sig check (Meta requires fast 200 ACK).

    Task acknowledgement:
      Expects message body format: "ACK {task_id}" or body containing
      a string matching a known task_id pattern.
      If task_id not found or task already ACKNOWLEDGED → no-op (idempotent).

    Never raises after sig check — all errors are swallowed best-effort.
    """
    # Step 1: Body + HMAC signature check
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_whatsapp_signature(body_bytes, signature):
        logger.warning("whatsapp_router: invalid or missing X-Hub-Signature-256")
        raise HTTPException(status_code=403, detail="invalid_signature")

    # Step 2: Parse body
    try:
        import json
        payload = json.loads(body_bytes)
    except Exception:
        # Meta sometimes sends non-JSON (status notifications) — 200 OK always
        return {"status": "ok", "processed": False}

    # Step 3: Extract task_id from message text (best-effort)
    task_id = _extract_task_id(payload)
    if task_id:
        _acknowledge_task_best_effort(request, task_id)

    # Step 4: 200 ACK to Meta
    return {"status": "ok", "processed": bool(task_id)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_task_id(payload: dict) -> str | None:
    """
    Extract task_id from a WhatsApp Cloud API webhook payload.

    Looks for message body text starting with "ACK " followed by a UUID-like string.
    Returns None if no valid task_id found.
    """
    try:
        entries = payload.get("entry") or []
        for entry in entries:
            changes = entry.get("changes") or []
            for change in changes:
                messages = (change.get("value") or {}).get("messages") or []
                for msg in messages:
                    body = (msg.get("text") or {}).get("body", "")
                    if body.upper().startswith("ACK "):
                        candidate = body[4:].strip()
                        if candidate:
                            return candidate
    except Exception:
        pass
    return None


def _acknowledge_task_best_effort(request: Request, task_id: str) -> None:
    """
    Attempt to acknowledge a task by task_id.

    Uses the Supabase client from request.app.state if available.
    Swallows all errors — WhatsApp ack must never block the 200 response.
    """
    try:
        db = getattr(getattr(request, "app", None), "state", None)
        db_client = getattr(db, "db", None) if db else None
        if not db_client:
            logger.debug("whatsapp_router: no db client available for task ack")
            return

        # Attempt PENDING → ACKNOWLEDGED transition
        result = (
            db_client.table("tasks")
            .update({"status": "ACKNOWLEDGED"})
            .eq("task_id", task_id)
            .eq("status", "PENDING")
            .execute()
        )
        updated = len(result.data or [])
        if updated:
            logger.info(
                "whatsapp_router: task acknowledged via WhatsApp. task_id=%s", task_id
            )
        else:
            logger.debug(
                "whatsapp_router: task ack no-op (already acked or not found). task_id=%s",
                task_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "whatsapp_router: task acknowledgement failed (best-effort). "
            "task_id=%s error=%s",
            task_id, exc,
        )
