"""
Phase 196 — WhatsApp Escalation Channel (Pure Module)

Pure Python module for building WhatsApp escalation payloads and deciding
whether to escalate a task via WhatsApp.

Architecture: Mirrors line_escalation.py exactly.

Contract:
    should_escalate(result: EscalationResult) -> bool
        Returns True if WhatsApp escalation should be triggered.
        True iff result.actions is non-empty and at least one action
        has reason="ACK_SLA_BREACH".

    build_whatsapp_message(task_row: dict) -> WhatsAppEscalationRequest
        Constructs the WhatsApp message payload from a task DB row.
        Does NOT send anything.

    format_whatsapp_text(task_row: dict) -> str
        Formats the human-readable WhatsApp message body.

Invariants (Phase 196):
    - PURE MODULE: No network calls, no DB reads/writes, no randomness.
    - Production dispatch (HTTP to Meta WhatsApp Cloud API) does NOT live here.
      This module only builds the payload structure.
    - Callers decide whether to actually send.
    - WhatsApp is fallback only. iHouse Core's tasks table
      is always the source of truth.
    - ACK_SLA_BREACH is the ONLY trigger that activates WhatsApp.
      COMPLETION_SLA_BREACH does NOT trigger WhatsApp escalation.
    - WhatsApp fires as a SECOND channel when LINE fails or tenant
      has whatsapp_enabled=True in permissions.

WhatsApp Cloud API (Meta):
    Endpoint: https://graph.facebook.com/v19.0/{phone_number_id}/messages
    Auth:     Authorization: Bearer {IHOUSE_WHATSAPP_TOKEN}
    Payload:  {"messaging_product": "whatsapp", "to": "{number}",
               "type": "text", "text": {"body": "..."}}

Env vars:
    IHOUSE_WHATSAPP_TOKEN           — Meta Cloud API bearer token
    IHOUSE_WHATSAPP_PHONE_NUMBER_ID — WhatsApp Business phone number ID
    IHOUSE_WHATSAPP_APP_SECRET      — HMAC-SHA256 sig verification secret
    IHOUSE_WHATSAPP_VERIFY_TOKEN    — Webhook challenge verification token

    Absent → dry-run mode (log warning, return sent=False, never crash).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tasks.sla_engine import EscalationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The only SLA trigger that activates external WhatsApp escalation.
#: Per architecture: WhatsApp fires only after in-app ACK SLA breached.
_WHATSAPP_TRIGGER = "ACK_SLA_BREACH"

#: Priority labels that should trigger WhatsApp escalation.
#: Low priority tasks do NOT escalate to WhatsApp.
_WHATSAPP_ELIGIBLE_PRIORITIES = {"HIGH", "CRITICAL", "High", "Critical", "urgent", "critical"}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WhatsAppEscalationRequest:
    """
    Immutable payload for a WhatsApp escalation message.

    This is built by build_whatsapp_message() and handed to the
    production dispatcher (which calls the Meta WhatsApp Cloud API).
    This module does NOT send — it only builds.
    """
    task_id: str
    property_id: str
    worker_role: str
    message_text: str
    priority: str
    trigger: str = _WHATSAPP_TRIGGER


@dataclass(frozen=True)
class WhatsAppDispatchResult:
    """
    Result returned by the production WhatsApp dispatcher (stub in tests).

    Fields:
        sent        — True if WhatsApp API call was attempted.
        task_id     — The task this dispatch was for.
        error       — Error message if dispatch failed, else None.
        dry_run     — True if dispatched in dry-run mode (no token).
    """
    sent: bool
    task_id: str
    error: Optional[str] = None
    dry_run: bool = False


# ---------------------------------------------------------------------------
# should_escalate
# ---------------------------------------------------------------------------

def should_escalate(result: EscalationResult) -> bool:
    """
    Return True if WhatsApp escalation should be triggered based on the
    SLA engine result.

    Conditions (ALL must be true):
    1. result.actions is non-empty.
    2. At least one action has reason == "ACK_SLA_BREACH".

    COMPLETION_SLA_BREACH does NOT trigger WhatsApp escalation.
    """
    if not result.actions:
        return False
    return any(a.reason == _WHATSAPP_TRIGGER for a in result.actions)


# ---------------------------------------------------------------------------
# build_whatsapp_message
# ---------------------------------------------------------------------------

def build_whatsapp_message(task_row: dict) -> WhatsAppEscalationRequest:
    """
    Build a WhatsAppEscalationRequest from a task DB row.

    Args:
        task_row: dict with keys: task_id, property_id, worker_role,
                  priority, urgency, title, due_date.

    Returns:
        WhatsAppEscalationRequest — pure payload, nothing is sent.
    """
    task_id = str(task_row.get("task_id") or "")
    property_id = str(task_row.get("property_id") or "")
    worker_role = str(task_row.get("worker_role") or "")
    priority = str(task_row.get("priority") or "")
    message_text = format_whatsapp_text(task_row)

    return WhatsAppEscalationRequest(
        task_id=task_id,
        property_id=property_id,
        worker_role=worker_role,
        message_text=message_text,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# format_whatsapp_text
# ---------------------------------------------------------------------------

def format_whatsapp_text(task_row: dict) -> str:
    """
    Format a human-readable WhatsApp message for the given task.

    Language: English (localisation is out of scope for Phase 196).
    Includes: task kind, property, due date, urgency.
    WhatsApp-native formatting: bold via *text*, no HTML.

    Args:
        task_row: dict with keys: title, kind, property_id, due_date,
                  urgency, worker_role.

    Returns:
        str — the message text to send via WhatsApp.
    """
    title = str(task_row.get("title") or "Task assigned")
    kind = str(task_row.get("kind") or "")
    property_id = str(task_row.get("property_id") or "")
    due_date = str(task_row.get("due_date") or "")
    urgency = str(task_row.get("urgency") or "normal")
    task_id = str(task_row.get("task_id") or "")

    lines = [
        "⚠️ *iHouse Task Escalation*",
        f"Task: {title}",
    ]
    if kind:
        lines.append(f"Type: {kind}")
    if property_id:
        lines.append(f"Property: {property_id}")
    if due_date:
        lines.append(f"Due: {due_date}")
    lines.append(f"Urgency: *{urgency.upper()}*")
    lines.append(f"Task ID: {task_id}")
    lines.append("Please acknowledge this task in the iHouse app.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Priority eligibility helper
# ---------------------------------------------------------------------------

def is_priority_eligible(task_row: dict) -> bool:
    """
    Return True if this task's priority is eligible for WhatsApp escalation.

    Low and Medium priority tasks do NOT get WhatsApp escalation.
    Only HIGH and CRITICAL (and their urgency equivalents) trigger WhatsApp.
    """
    priority = str(task_row.get("priority") or "")
    urgency = str(task_row.get("urgency") or "")
    return priority in _WHATSAPP_ELIGIBLE_PRIORITIES or urgency in _WHATSAPP_ELIGIBLE_PRIORITIES


# ---------------------------------------------------------------------------
# HMAC signature verification (for inbound webhook)
# ---------------------------------------------------------------------------

def verify_whatsapp_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Verify X-Hub-Signature-256 from Meta WhatsApp webhook.

    Args:
        payload_bytes:    Raw request body bytes.
        signature_header: Value of X-Hub-Signature-256 header (e.g. "sha256=abc...")

    Returns:
        True if signature is valid, False otherwise.
        Always returns False if IHOUSE_WHATSAPP_APP_SECRET is not set.
    """
    app_secret = os.environ.get("IHOUSE_WHATSAPP_APP_SECRET", "")
    if not app_secret:
        logger.warning(
            "whatsapp_escalation: IHOUSE_WHATSAPP_APP_SECRET not set — "
            "signature verification will always fail."
        )
        return False

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_sig = signature_header[len("sha256="):]
    computed = hmac.new(
        app_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, expected_sig)


# ---------------------------------------------------------------------------
# Dry-run dispatch (no-op when token absent)
# ---------------------------------------------------------------------------

def dispatch_dry_run(request: WhatsAppEscalationRequest) -> WhatsAppDispatchResult:
    """
    Return a dry-run result when IHOUSE_WHATSAPP_TOKEN is not configured.

    Used in dev/test environments. Logs a warning but never raises.
    """
    logger.warning(
        "whatsapp_escalation: IHOUSE_WHATSAPP_TOKEN not set — "
        "WhatsApp dispatch skipped (dry-run). task_id=%s",
        request.task_id,
    )
    return WhatsAppDispatchResult(
        sent=False,
        task_id=request.task_id,
        error=None,
        dry_run=True,
    )
