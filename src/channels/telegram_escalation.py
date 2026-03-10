"""
Phase 203 — Telegram Escalation Channel (Pure Module)

Pure Python module for building Telegram Bot API escalation payloads and
deciding whether to escalate task notifications via Telegram.

Mirrors the architecture of line_escalation.py exactly:
    - Pure module: no network calls, no DB reads/writes, no randomness.
    - Production dispatch (HTTP POST to api.telegram.org) does NOT live here.
      This module only builds the payload structure.
    - Callers decide whether to actually send.

Contract:
    should_escalate(result: EscalationResult) -> bool
        Returns True if Telegram escalation should be triggered.
        True iff result.actions is non-empty and at least one action
        has reason="ACK_SLA_BREACH".

    build_telegram_message(task_row: dict) -> TelegramEscalationRequest
        Constructs the Telegram Bot API payload from a task DB row.
        Does NOT send anything.

    format_telegram_text(task_row: dict) -> str
        Formats the human-readable Telegram message body (Markdown).

    is_priority_eligible(task_row: dict) -> bool
        Returns True if the task priority warrants Telegram escalation.
        Only HIGH and CRITICAL are eligible.

Invariants (Phase 203):
    - PURE MODULE: No network calls, no DB reads/writes, no randomness.
    - Telegram is a tier-1 preferred external channel (per notification_dispatcher.py).
    - ACK_SLA_BREACH is the ONLY trigger reason that activates Telegram escalation.
      COMPLETION_SLA_BREACH does NOT trigger Telegram escalation.
    - parse_mode is always "Markdown" (Telegram Bot API v1 format).
    - chat_id comes from notification_channels.channel_id for this user.
    - LOW and MEDIUM priority tasks do NOT escalate to Telegram.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from tasks.sla_engine import EscalationResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The only SLA trigger that activates Telegram escalation.
#: Mirrors ACK_SLA_BREACH trigger used by line_escalation.py.
_TELEGRAM_TRIGGER = "ACK_SLA_BREACH"

#: Priority levels that are eligible for Telegram escalation.
#: LOW and MEDIUM tasks do NOT escalate externally.
_TELEGRAM_ELIGIBLE_PRIORITIES = {"HIGH", "CRITICAL", "High", "Critical", "urgent", "critical"}

#: Telegram Bot API parse_mode — enables *bold* and _italic_ formatting.
TELEGRAM_PARSE_MODE = "Markdown"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TelegramEscalationRequest:
    """
    Immutable payload for a Telegram escalation message.

    This is built by build_telegram_message() and handed to the
    production dispatcher (which calls the Telegram Bot API).
    This module does NOT send — it only builds.

    Telegram Bot API equivalent:
        POST https://api.telegram.org/bot{TOKEN}/sendMessage
        {
            "chat_id": <chat_id>,
            "text": <text>,
            "parse_mode": "Markdown"
        }
    """
    task_id: str
    property_id: str
    worker_role: str
    chat_id: str           # Telegram chat_id from notification_channels.channel_id
    text: str              # Markdown-formatted message body
    parse_mode: str        # Always "Markdown"
    priority: str
    trigger: str = _TELEGRAM_TRIGGER


@dataclass(frozen=True)
class TelegramDispatchResult:
    """
    Result returned by the production Telegram dispatcher.

    Fields:
        sent      — True if Telegram API call was attempted.
        task_id   — The task this dispatch was for.
        error     — Error message if dispatch failed, else None.
    """
    sent: bool
    task_id: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# should_escalate
# ---------------------------------------------------------------------------

def should_escalate(result: EscalationResult) -> bool:
    """
    Return True if Telegram escalation should be triggered.

    Conditions (ALL must be true):
    1. result.actions is non-empty.
    2. At least one action has reason == "ACK_SLA_BREACH".

    COMPLETION_SLA_BREACH does NOT trigger Telegram escalation.
    Mirrors line_escalation.should_escalate exactly.
    """
    if not result.actions:
        return False
    return any(a.reason == _TELEGRAM_TRIGGER for a in result.actions)


# ---------------------------------------------------------------------------
# build_telegram_message
# ---------------------------------------------------------------------------

def build_telegram_message(task_row: dict, chat_id: str) -> TelegramEscalationRequest:
    """
    Build a TelegramEscalationRequest from a task DB row.

    Args:
        task_row: dict with keys: task_id, property_id, worker_role,
                  priority, urgency, title, due_date.
        chat_id:  The Telegram chat_id for this worker (from notification_channels).

    Returns:
        TelegramEscalationRequest — pure payload, nothing is sent.
    """
    task_id = str(task_row.get("task_id") or "")
    property_id = str(task_row.get("property_id") or "")
    worker_role = str(task_row.get("worker_role") or "")
    priority = str(task_row.get("priority") or "")
    text = format_telegram_text(task_row)

    return TelegramEscalationRequest(
        task_id=task_id,
        property_id=property_id,
        worker_role=worker_role,
        chat_id=chat_id,
        text=text,
        parse_mode=TELEGRAM_PARSE_MODE,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# format_telegram_text
# ---------------------------------------------------------------------------

def format_telegram_text(task_row: dict) -> str:
    """
    Format a Markdown-formatted Telegram message for the given task.

    Uses Telegram Bot API Markdown (v1):
        *text* = bold
        _text_ = italic

    Language: English (localisation out of scope for Phase 203).
    Includes: task kind, property, due date, urgency, task ID.

    Args:
        task_row: dict with keys: title, kind, property_id, due_date,
                  urgency, worker_role, task_id.

    Returns:
        str — Markdown-formatted message text to send via Telegram.
    """
    title = str(task_row.get("title") or "Task assigned")
    kind = str(task_row.get("kind") or "")
    property_id = str(task_row.get("property_id") or "")
    due_date = str(task_row.get("due_date") or "")
    urgency = str(task_row.get("urgency") or "normal")
    task_id = str(task_row.get("task_id") or "")

    lines = [
        "*⚠️  iHouse Task Escalation*",
        f"*Task:* {title}",
    ]
    if kind:
        lines.append(f"*Type:* {kind}")
    if property_id:
        lines.append(f"*Property:* {property_id}")
    if due_date:
        lines.append(f"*Due:* {due_date}")
    lines.append(f"*Urgency:* {urgency.upper()}")
    lines.append(f"_Task ID: {task_id}_")
    lines.append("Please acknowledge this task in the iHouse app.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Priority eligibility helper
# ---------------------------------------------------------------------------

def is_priority_eligible(task_row: dict) -> bool:
    """
    Return True if this task's priority is eligible for Telegram escalation.

    LOW and MEDIUM priority tasks do NOT get Telegram escalation.
    Only HIGH and CRITICAL (and their urgency equivalents) trigger Telegram.
    Mirrors line_escalation.is_priority_eligible exactly.
    """
    priority = str(task_row.get("priority") or "")
    urgency = str(task_row.get("urgency") or "")
    return priority in _TELEGRAM_ELIGIBLE_PRIORITIES or urgency in _TELEGRAM_ELIGIBLE_PRIORITIES
