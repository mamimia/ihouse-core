"""
Phase 212 — SMS Escalation Channel (Pure Module)

Pure Python module for building SMS escalation payloads and deciding
whether to escalate task notifications via SMS.

Mirrors the architecture of telegram_escalation.py exactly:
    - Pure module: no network calls, no DB reads/writes, no randomness.
    - Production dispatch (HTTP POST to Twilio / AWS SNS) does NOT live here.
      This module only builds the payload structure.
    - Callers decide whether to actually send.

Contract:
    should_escalate(result: EscalationResult) -> bool
        Returns True if SMS escalation should be triggered.
        True iff result.actions is non-empty and at least one action
        has reason="ACK_SLA_BREACH".

    build_sms_message(task_row: dict, to_number: str) -> SMSEscalationRequest
        Constructs the SMS payload from a task DB row.
        Does NOT send anything.

    format_sms_text(task_row: dict) -> str
        Formats the human-readable SMS message body.
        Plain text only — no markdown (SMS does not render formatting).

    is_priority_eligible(task_row: dict) -> bool
        Returns True if the task priority warrants SMS escalation.
        Only HIGH and CRITICAL are eligible.

Invariants (Phase 212):
    - PURE MODULE: No network calls, no DB reads/writes, no randomness.
    - SMS is a tier-2 last-resort channel. It fires ONLY after Tier-1
      channels (LINE, WhatsApp, Telegram) have failed or are unavailable.
    - ACK_SLA_BREACH is the ONLY trigger reason that activates SMS escalation.
      COMPLETION_SLA_BREACH does NOT trigger SMS escalation.
    - Message body is plain text only. SMS cannot render bold/italic.
    - to_number is the E.164-formatted phone number from notification_channels.channel_id.
    - LOW and MEDIUM priority tasks do NOT escalate to SMS.
    - Dry-run mode (no IHOUSE_SMS_TOKEN set): logs warning, returns sent=False.

Provider:
    Designed for Twilio REST API (primary) or AWS SNS (fallback).
    Env vars:
        IHOUSE_SMS_TOKEN      — Twilio auth token or AWS secret key
        IHOUSE_SMS_ACCOUNT_SID— Twilio account SID (Twilio only)
        IHOUSE_SMS_FROM_NUMBER— E.164 sender number (e.g. +1415XXXXXXX)

    Absent → dry-run mode (log warning, return sent=False, never crash).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from tasks.sla_engine import EscalationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The only SLA trigger that activates SMS escalation.
#: Mirrors ACK_SLA_BREACH trigger used by all other external channels.
_SMS_TRIGGER = "ACK_SLA_BREACH"

#: Priority levels that are eligible for SMS escalation.
#: LOW and MEDIUM tasks do NOT escalate externally via SMS.
_SMS_ELIGIBLE_PRIORITIES = {"HIGH", "CRITICAL", "High", "Critical", "urgent", "critical"}

#: Maximum SMS body length (160 chars for single-part, 1600 for concatenated).
#: We target single-part to avoid carrier fragmentation issues.
SMS_MAX_LENGTH = 160


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SMSEscalationRequest:
    """
    Immutable payload for an SMS escalation message.

    This is built by build_sms_message() and handed to the
    production dispatcher (which calls Twilio or AWS SNS).
    This module does NOT send — it only builds.

    Twilio REST API equivalent:
        POST https://api.twilio.com/2010-04-01/Accounts/{AccountSid}/Messages.json
        {
            "From": "<from_number>",
            "To":   "<to_number>",
            "Body": "<body>"
        }
    """
    task_id: str
    property_id: str
    worker_role: str
    to_number: str       # E.164 recipient phone number from notification_channels.channel_id
    body: str            # Plain text message body
    priority: str
    trigger: str = _SMS_TRIGGER


@dataclass(frozen=True)
class SMSDispatchResult:
    """
    Result returned by the production SMS dispatcher.

    Fields:
        sent      — True if SMS API call was attempted and accepted.
        task_id   — The task this dispatch was for.
        error     — Error message if dispatch failed, else None.
        dry_run   — True if dispatched in dry-run mode (no token configured).
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
    Return True if SMS escalation should be triggered.

    Conditions (ALL must be true):
    1. result.actions is non-empty.
    2. At least one action has reason == "ACK_SLA_BREACH".

    COMPLETION_SLA_BREACH does NOT trigger SMS escalation.
    Mirrors telegram_escalation.should_escalate exactly.
    """
    if not result.actions:
        return False
    return any(a.reason == _SMS_TRIGGER for a in result.actions)


# ---------------------------------------------------------------------------
# build_sms_message
# ---------------------------------------------------------------------------

def build_sms_message(task_row: dict, to_number: str) -> SMSEscalationRequest:
    """
    Build an SMSEscalationRequest from a task DB row.

    Args:
        task_row:  dict with keys: task_id, property_id, worker_role,
                   priority, urgency, title, due_date.
        to_number: E.164 phone number for the recipient (from notification_channels).

    Returns:
        SMSEscalationRequest — pure payload, nothing is sent.
    """
    task_id = str(task_row.get("task_id") or "")
    property_id = str(task_row.get("property_id") or "")
    worker_role = str(task_row.get("worker_role") or "")
    priority = str(task_row.get("priority") or "")
    body = format_sms_text(task_row)

    return SMSEscalationRequest(
        task_id=task_id,
        property_id=property_id,
        worker_role=worker_role,
        to_number=to_number,
        body=body,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# format_sms_text
# ---------------------------------------------------------------------------

def format_sms_text(task_row: dict) -> str:
    """
    Format a plain-text SMS message for the given task.

    Plain text only — SMS cannot render markdown, bold, or italic.
    Targets single-part length (≤160 chars) when possible.

    Args:
        task_row: dict with keys: title, kind, property_id, due_date,
                  urgency, task_id.

    Returns:
        str — plain text message body to send via SMS.
    """
    title = str(task_row.get("title") or "Task assigned")
    property_id = str(task_row.get("property_id") or "")
    urgency = str(task_row.get("urgency") or "normal")
    task_id = str(task_row.get("task_id") or "")

    # Keep it short for single-part SMS (160 chars).
    # Omit kind and due_date to stay under the limit.
    parts = [
        "iHouse URGENT: " + title,
    ]
    if property_id:
        parts.append(f"Prop: {property_id}")
    parts.append(f"Urgency: {urgency.upper()}")
    parts.append(f"Task: {task_id[:8]}")  # truncated UUID for brevity
    parts.append("Reply ACK to confirm.")

    body = " | ".join(parts)

    # Trim to SMS_MAX_LENGTH — best-effort
    if len(body) > SMS_MAX_LENGTH:
        body = body[:SMS_MAX_LENGTH - 3] + "..."

    return body


# ---------------------------------------------------------------------------
# Priority eligibility helper
# ---------------------------------------------------------------------------

def is_priority_eligible(task_row: dict) -> bool:
    """
    Return True if this task's priority is eligible for SMS escalation.

    LOW and MEDIUM priority tasks do NOT get SMS escalation.
    Only HIGH and CRITICAL (and their urgency equivalents) trigger SMS.
    Mirrors telegram_escalation.is_priority_eligible exactly.
    """
    priority = str(task_row.get("priority") or "")
    urgency = str(task_row.get("urgency") or "")
    return priority in _SMS_ELIGIBLE_PRIORITIES or urgency in _SMS_ELIGIBLE_PRIORITIES


# ---------------------------------------------------------------------------
# Dry-run dispatch (no-op when token absent)
# ---------------------------------------------------------------------------

def dispatch_dry_run(request: SMSEscalationRequest) -> SMSDispatchResult:
    """
    Return a dry-run result when IHOUSE_SMS_TOKEN is not configured.

    Used in dev/test environments. Logs a warning but never raises.
    """
    logger.warning(
        "sms_escalation: IHOUSE_SMS_TOKEN not set — "
        "SMS dispatch skipped (dry-run). task_id=%s",
        request.task_id,
    )
    return SMSDispatchResult(
        sent=False,
        task_id=request.task_id,
        error=None,
        dry_run=True,
    )
