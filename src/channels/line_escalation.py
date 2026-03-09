"""
Phase 124 — LINE Escalation Channel (Pure Module)

Pure Python module for building LINE escalation payloads and deciding
whether to escalate a task via LINE.

Contract:
    should_escalate(result: EscalationResult) -> bool
        Returns True if LINE escalation should be triggered.
        True iff result.actions is non-empty and at least one action
        has reason="ACK_SLA_BREACH".

    build_line_message(task_row: dict) -> LineEscalationRequest
        Constructs the LINE message payload from a task DB row.
        Does NOT send anything.

    format_line_text(task_row: dict) -> str
        Formats the human-readable LINE message body.

Invariants (Phase 124):
    - PURE MODULE: No network calls, no DB reads/writes, no randomness.
    - Production dispatch (HTTP to LINE Messaging API) does NOT live here.
      This module only builds the payload structure.
    - Callers decide whether to actually send.
    - LINE is fallback only. iHouse Core's tasks table
      is always the source of truth.
    - ACK_SLA_BREACH is the ONLY trigger that activates LINE.
      COMPLETION_SLA_BREACH does NOT trigger LINE escalation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from tasks.sla_engine import EscalationResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: The only SLA trigger that activates external LINE escalation.
#: Per worker-communication-layer.md: LINE fires only after in-app ACK SLA breached.
_LINE_TRIGGER = "ACK_SLA_BREACH"

#: Priority labels that should trigger LINE escalation.
#: Low priority tasks do NOT escalate to LINE.
_LINE_ELIGIBLE_PRIORITIES = {"HIGH", "CRITICAL", "High", "Critical", "urgent", "critical"}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineEscalationRequest:
    """
    Immutable payload for a LINE escalation message.

    This is built by build_line_message() and handed to the
    production dispatcher (which calls the LINE Messaging API).
    This module does NOT send — it only builds.
    """
    task_id: str
    property_id: str
    worker_role: str
    message_text: str
    priority: str
    trigger: str = _LINE_TRIGGER


@dataclass(frozen=True)
class LineDispatchResult:
    """
    Result returned by the production LINE dispatcher (stub in tests).

    Fields:
        sent        — True if LINE API call was attempted.
        task_id     — The task this dispatch was for.
        error       — Error message if dispatch failed, else None.
    """
    sent: bool
    task_id: str
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# should_escalate
# ---------------------------------------------------------------------------

def should_escalate(result: EscalationResult) -> bool:
    """
    Return True if LINE escalation should be triggered based on the
    SLA engine result.

    Conditions (ALL must be true):
    1. result.actions is non-empty.
    2. At least one action has reason == "ACK_SLA_BREACH".

    COMPLETION_SLA_BREACH does NOT trigger LINE escalation.
    """
    if not result.actions:
        return False
    return any(a.reason == _LINE_TRIGGER for a in result.actions)


# ---------------------------------------------------------------------------
# build_line_message
# ---------------------------------------------------------------------------

def build_line_message(task_row: dict) -> LineEscalationRequest:
    """
    Build a LineEscalationRequest from a task DB row.

    Args:
        task_row: dict with keys: task_id, property_id, worker_role,
                  priority, urgency, title, due_date.

    Returns:
        LineEscalationRequest — pure payload, nothing is sent.
    """
    task_id = str(task_row.get("task_id") or "")
    property_id = str(task_row.get("property_id") or "")
    worker_role = str(task_row.get("worker_role") or "")
    priority = str(task_row.get("priority") or "")
    message_text = format_line_text(task_row)

    return LineEscalationRequest(
        task_id=task_id,
        property_id=property_id,
        worker_role=worker_role,
        message_text=message_text,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# format_line_text
# ---------------------------------------------------------------------------

def format_line_text(task_row: dict) -> str:
    """
    Format a human-readable LINE message for the given task.

    Language: English (localisation is out of scope for Phase 124).
    Includes: task kind, property, due date, urgency.

    Args:
        task_row: dict with keys: title, kind, property_id, due_date,
                  urgency, worker_role.

    Returns:
        str — the message text to send via LINE.
    """
    title = str(task_row.get("title") or "Task assigned")
    kind = str(task_row.get("kind") or "")
    property_id = str(task_row.get("property_id") or "")
    due_date = str(task_row.get("due_date") or "")
    urgency = str(task_row.get("urgency") or "normal")
    task_id = str(task_row.get("task_id") or "")

    lines = [
        f"⚠️  iHouse Task Escalation",
        f"Task: {title}",
    ]
    if kind:
        lines.append(f"Type: {kind}")
    if property_id:
        lines.append(f"Property: {property_id}")
    if due_date:
        lines.append(f"Due: {due_date}")
    lines.append(f"Urgency: {urgency.upper()}")
    lines.append(f"Task ID: {task_id}")
    lines.append("Please acknowledge this task in the iHouse app.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Priority eligibility helper
# ---------------------------------------------------------------------------

def is_priority_eligible(task_row: dict) -> bool:
    """
    Return True if this task's priority is eligible for LINE escalation.

    Low and Medium priority tasks do NOT get LINE escalation.
    Only HIGH and CRITICAL (and their urgency equivalents) trigger LINE.
    """
    priority = str(task_row.get("priority") or "")
    urgency = str(task_row.get("urgency") or "")
    return priority in _LINE_ELIGIBLE_PRIORITIES or urgency in _LINE_ELIGIBLE_PRIORITIES
