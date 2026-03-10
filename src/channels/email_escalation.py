"""
Phase 213 — Email Notification Channel (Pure Module)

Pure Python module for building email escalation payloads and deciding
whether to escalate task notifications via email.

Mirrors the architecture of sms_escalation.py exactly:
    - Pure module: no network calls, no DB reads/writes, no randomness.
    - Production dispatch (SMTP / SendGrid / AWS SES) does NOT live here.
      This module only builds the payload structure.
    - Callers decide whether to actually send.

Contract:
    should_escalate(result: EscalationResult) -> bool
        Returns True if email escalation should be triggered.
        True iff result.actions is non-empty and at least one action
        has reason="ACK_SLA_BREACH".

    build_email_message(task_row: dict, to_address: str) -> EmailEscalationRequest
        Constructs the email payload from a task DB row.
        Does NOT send anything.

    format_email_subject(task_row: dict) -> str
        Formats the email subject line.

    format_email_body(task_row: dict) -> str
        Formats the plain-text email body.

    is_priority_eligible(task_row: dict) -> bool
        Returns True if the task priority warrants email escalation.
        Only HIGH and CRITICAL are eligible.

Invariants (Phase 213):
    - PURE MODULE: No network calls, no DB reads/writes, no randomness.
    - Email is a tier-1 fallback channel, also used for owner-facing
      communications (owner statements, financial reports).
    - ACK_SLA_BREACH is the ONLY trigger reason that activates task-level
      email escalation. COMPLETION_SLA_BREACH does NOT trigger email.
    - Body is plain text. HTML templates are out of scope for Phase 213.
    - to_address is the email address from notification_channels.channel_id.
    - LOW and MEDIUM priority tasks do NOT escalate via email.
    - Dry-run mode (no IHOUSE_EMAIL_TOKEN set): logs warning, returns sent=False.

Provider:
    Designed for SMTP (primary) or SendGrid / AWS SES (fallback).
    Env vars:
        IHOUSE_EMAIL_TOKEN      — SMTP password or API key
        IHOUSE_EMAIL_FROM       — Sender address (e.g. alerts@ihouse.app)
        IHOUSE_EMAIL_SMTP_HOST  — SMTP host (e.g. smtp.sendgrid.net)
        IHOUSE_EMAIL_SMTP_PORT  — SMTP port (default: 587)

    Absent → dry-run mode (log warning, return sent=False, never crash).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from tasks.sla_engine import EscalationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The only SLA trigger that activates email escalation for tasks.
_EMAIL_TRIGGER = "ACK_SLA_BREACH"

#: Priority levels eligible for email escalation.
_EMAIL_ELIGIBLE_PRIORITIES = {"HIGH", "CRITICAL", "High", "Critical", "urgent", "critical"}

#: Default sender display name
EMAIL_FROM_NAME = "iHouse Alerts"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EmailEscalationRequest:
    """
    Immutable payload for an email escalation message.

    This is built by build_email_message() and handed to the production
    dispatcher (which calls SMTP / SendGrid / AWS SES).
    This module does NOT send — it only builds.

    SMTP equivalent:
        From:    IHOUSE_EMAIL_FROM
        To:      to_address
        Subject: subject
        Body:    body (plain text)
    """
    task_id: str
    property_id: str
    worker_role: str
    to_address: str      # Recipient email (from notification_channels.channel_id)
    subject: str
    body: str            # Plain text email body
    priority: str
    trigger: str = _EMAIL_TRIGGER


@dataclass(frozen=True)
class EmailDispatchResult:
    """
    Result returned by the production email dispatcher.

    Fields:
        sent      — True if email API/SMTP call was accepted.
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
    Return True if email escalation should be triggered.

    Conditions (ALL must be true):
    1. result.actions is non-empty.
    2. At least one action has reason == "ACK_SLA_BREACH".

    COMPLETION_SLA_BREACH does NOT trigger email escalation.
    Mirrors sms_escalation.should_escalate exactly.
    """
    if not result.actions:
        return False
    return any(a.reason == _EMAIL_TRIGGER for a in result.actions)


# ---------------------------------------------------------------------------
# build_email_message
# ---------------------------------------------------------------------------

def build_email_message(task_row: dict, to_address: str) -> EmailEscalationRequest:
    """
    Build an EmailEscalationRequest from a task DB row.

    Args:
        task_row:   dict with keys: task_id, property_id, worker_role,
                    priority, urgency, title, kind, due_date.
        to_address: Recipient email address (from notification_channels).

    Returns:
        EmailEscalationRequest — pure payload, nothing is sent.
    """
    task_id = str(task_row.get("task_id") or "")
    property_id = str(task_row.get("property_id") or "")
    worker_role = str(task_row.get("worker_role") or "")
    priority = str(task_row.get("priority") or "")
    subject = format_email_subject(task_row)
    body = format_email_body(task_row)

    return EmailEscalationRequest(
        task_id=task_id,
        property_id=property_id,
        worker_role=worker_role,
        to_address=to_address,
        subject=subject,
        body=body,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# format_email_subject
# ---------------------------------------------------------------------------

def format_email_subject(task_row: dict) -> str:
    """
    Format the email subject line for the given task.

    Args:
        task_row: dict with keys: title, priority, urgency, property_id.

    Returns:
        str — concise subject line.
    """
    title = str(task_row.get("title") or "Task assigned")
    priority = str(task_row.get("priority") or "")
    property_id = str(task_row.get("property_id") or "")

    prefix = "[URGENT] " if priority in _EMAIL_ELIGIBLE_PRIORITIES else ""
    suffix = f" — {property_id}" if property_id else ""
    return f"{prefix}iHouse: {title}{suffix}"


# ---------------------------------------------------------------------------
# format_email_body
# ---------------------------------------------------------------------------

def format_email_body(task_row: dict) -> str:
    """
    Format a plain-text email body for the given task.

    Plain text only — HTML templates are out of scope for Phase 213.
    Includes full task details: title, kind, property, due date, urgency,
    task ID. More verbose than SMS since email has no character limit.

    Args:
        task_row: dict with keys: title, kind, property_id, due_date,
                  urgency, worker_role, task_id, priority.

    Returns:
        str — plain text email body.
    """
    title = str(task_row.get("title") or "Task assigned")
    kind = str(task_row.get("kind") or "")
    property_id = str(task_row.get("property_id") or "")
    due_date = str(task_row.get("due_date") or "")
    urgency = str(task_row.get("urgency") or "normal")
    worker_role = str(task_row.get("worker_role") or "")
    task_id = str(task_row.get("task_id") or "")
    priority = str(task_row.get("priority") or "")

    lines = [
        "iHouse — Task Escalation Notice",
        "=" * 40,
        "",
        f"Task: {title}",
    ]
    if kind:
        lines.append(f"Type: {kind}")
    if property_id:
        lines.append(f"Property: {property_id}")
    if worker_role:
        lines.append(f"Assigned to: {worker_role}")
    if due_date:
        lines.append(f"Due: {due_date}")
    lines.append(f"Priority: {priority.upper() if priority else 'UNKNOWN'}")
    lines.append(f"Urgency: {urgency.upper()}")
    lines.append("")
    lines.append(f"Task ID: {task_id}")
    lines.append("")
    lines.append(
        "This task requires immediate acknowledgement. "
        "Please open the iHouse app and acknowledge this task to stop further escalation."
    )
    lines.append("")
    lines.append("---")
    lines.append("This is an automated alert from iHouse Core.")
    lines.append("Do not reply to this email.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Priority eligibility helper
# ---------------------------------------------------------------------------

def is_priority_eligible(task_row: dict) -> bool:
    """
    Return True if this task's priority is eligible for email escalation.

    LOW and MEDIUM priority tasks do NOT get email escalation.
    Only HIGH and CRITICAL (and their urgency equivalents) trigger email.
    Mirrors sms_escalation.is_priority_eligible exactly.
    """
    priority = str(task_row.get("priority") or "")
    urgency = str(task_row.get("urgency") or "")
    return priority in _EMAIL_ELIGIBLE_PRIORITIES or urgency in _EMAIL_ELIGIBLE_PRIORITIES


# ---------------------------------------------------------------------------
# Dry-run dispatch (no-op when token absent)
# ---------------------------------------------------------------------------

def dispatch_dry_run(request: EmailEscalationRequest) -> EmailDispatchResult:
    """
    Return a dry-run result when IHOUSE_EMAIL_TOKEN is not configured.

    Used in dev/test environments. Logs a warning but never raises.
    """
    logger.warning(
        "email_escalation: IHOUSE_EMAIL_TOKEN not set — "
        "email dispatch skipped (dry-run). task_id=%s to=%s",
        request.task_id,
        request.to_address,
    )
    return EmailDispatchResult(
        sent=False,
        task_id=request.task_id,
        error=None,
        dry_run=True,
    )
