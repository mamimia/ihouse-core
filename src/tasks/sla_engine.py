"""
Phase 117 — SLA Escalation Engine

Pure Python implementation of the SLA escalation skill
(.agent/skills/sla-escalation-engine/SKILL.md).

Contract:
    evaluate(payload: dict) -> EscalationResult

Key invariants:
    1. No implicit time. Caller supplies now_utc and due timestamps.
    2. No storage reads or writes.
    3. No network calls.
    4. No randomness — output is a deterministic function of input.
    5. Terminal task states (Completed, Cancelled) emit audit only,
       never emit escalation actions.
    6. Critical acknowledgement SLA is fixed at 5 minutes.
       The engine does NOT compute task_ack_due_utc — caller must.

Input shape (dict):
    {
      "actor": {"actor_id": str, "role": str},
      "context": {
          "run_id": str,
          "timers_utc": {
              "now_utc": str,               # ISO-8601 UTC timestamp
              "task_ack_due_utc": str,      # ISO-8601 or "" if not applicable
              "task_completed_due_utc": str # ISO-8601 or "" if not applicable
          }
      },
      "task": {
          "task_id":    str,
          "property_id": str,
          "task_type":  str,
          "state":      "Open" | "InProgress" | "Completed" | "Cancelled",
          "priority":   "Normal" | "High" | "Critical",
          "ack_state":  "Unacked" | "Acked"
      },
      "policy": {
          "notify_ops_on":   list[str],   # trigger names that alert ops
          "notify_admin_on": list[str]    # trigger names that alert admin
      },
      "idempotency": {"request_id": str}
    }

Output (EscalationResult):
    .actions         — list of EscalationAction
    .audit_event     — dict (AuditEvent)
    .side_effects    — always []

Trigger types emitted:
    ACK_SLA_BREACH         — ack_state == "Unacked" and now_utc >= task_ack_due_utc
    COMPLETION_SLA_BREACH  — now_utc >= task_completed_due_utc and state != "Completed"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EscalationAction:
    action_type: str    # "notify_ops" | "notify_admin"
    target: str         # "ops" | "admin"
    reason: str         # trigger name, e.g. "ACK_SLA_BREACH"
    task_id: str
    property_id: str
    request_id: str


@dataclass(frozen=True)
class EscalationResult:
    actions: List[EscalationAction]
    audit_event: Dict[str, Any]
    side_effects: List[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fixed constants (from skill spec)
# ---------------------------------------------------------------------------

CRITICAL_ACK_SLA_MINUTES: int = 5
_TERMINAL_STATES: frozenset[str] = frozenset({"Completed", "Cancelled"})
_TRIGGER_ACK: str = "ACK_SLA_BREACH"
_TRIGGER_COMPLETION: str = "COMPLETION_SLA_BREACH"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _str(v: Any) -> str:
    """Safely coerce a value to str, returning '' on None/missing."""
    if v is None:
        return ""
    return str(v)


def _nonempty(s: str) -> bool:
    return bool(s and s.strip())


def _strset(lst: Any) -> Set[str]:
    if not isinstance(lst, list):
        return set()
    return {str(x) for x in lst}


# ---------------------------------------------------------------------------
# Core evaluation function
# ---------------------------------------------------------------------------

def evaluate(payload: Dict[str, Any]) -> EscalationResult:
    """
    Deterministic SLA escalation evaluation.

    Args:
        payload: structured dict per the contract above.

    Returns:
        EscalationResult with actions, audit_event, and side_effects=[].

    Raises:
        KeyError | TypeError if required fields are missing or malformed.
        Caller is responsible for validating payload shape.
    """
    # --- Unpack ---
    idempotency = payload["idempotency"]
    req_id = _str(idempotency["request_id"])

    actor: Dict[str, Any] = payload.get("actor") or {}
    actor_id = _str(actor.get("actor_id"))
    role = _str(actor.get("role"))

    context: Dict[str, Any] = payload.get("context") or {}
    run_id = _str(context.get("run_id"))
    timers: Dict[str, Any] = context.get("timers_utc") or {}
    now_utc = _str(timers["now_utc"])
    ack_due = _str(timers.get("task_ack_due_utc") or "")
    completed_due = _str(timers.get("task_completed_due_utc") or "")

    task: Dict[str, Any] = payload.get("task") or {}
    task_id = _str(task.get("task_id"))
    prop_id = _str(task.get("property_id"))
    task_type = _str(task.get("task_type"))
    state = _str(task.get("state"))
    priority = _str(task.get("priority"))
    ack_state = _str(task.get("ack_state"))

    policy: Dict[str, Any] = payload.get("policy") or {}
    notify_ops_on: Set[str] = _strset(policy.get("notify_ops_on"))
    notify_admin_on: Set[str] = _strset(policy.get("notify_admin_on"))

    # --- Evaluate triggers ---
    triggers: List[str] = []
    actions: List[EscalationAction] = []

    terminal = state in _TERMINAL_STATES

    if not terminal:
        # ACK SLA breach
        if ack_state == "Unacked" and _nonempty(ack_due) and now_utc >= ack_due:
            triggers.append(_TRIGGER_ACK)
            if _TRIGGER_ACK in notify_ops_on:
                actions.append(EscalationAction(
                    action_type="notify_ops",
                    target="ops",
                    reason=_TRIGGER_ACK,
                    task_id=task_id,
                    property_id=prop_id,
                    request_id=req_id,
                ))
            if _TRIGGER_ACK in notify_admin_on:
                actions.append(EscalationAction(
                    action_type="notify_admin",
                    target="admin",
                    reason=_TRIGGER_ACK,
                    task_id=task_id,
                    property_id=prop_id,
                    request_id=req_id,
                ))

        # Completion SLA breach
        if _nonempty(completed_due) and now_utc >= completed_due and state != "Completed":
            triggers.append(_TRIGGER_COMPLETION)
            if _TRIGGER_COMPLETION in notify_ops_on:
                actions.append(EscalationAction(
                    action_type="notify_ops",
                    target="ops",
                    reason=_TRIGGER_COMPLETION,
                    task_id=task_id,
                    property_id=prop_id,
                    request_id=req_id,
                ))
            if _TRIGGER_COMPLETION in notify_admin_on:
                actions.append(EscalationAction(
                    action_type="notify_admin",
                    target="admin",
                    reason=_TRIGGER_COMPLETION,
                    task_id=task_id,
                    property_id=prop_id,
                    request_id=req_id,
                ))

    # --- Build audit event ---
    audit_event: Dict[str, Any] = {
        "event_type": "AuditEvent",
        "request_id": req_id,
        "run_id": run_id,
        "now_utc": now_utc,
        "actor_id": actor_id,
        "role": role,
        "task": {
            "task_id": task_id,
            "property_id": prop_id,
            "task_type": task_type,
            "state": state,
            "priority": priority,
            "ack_state": ack_state,
        },
        "timers_utc": {
            "task_ack_due_utc": ack_due,
            "task_completed_due_utc": completed_due,
        },
        "triggers_fired": triggers,
        "actions_emitted": [
            {"action_type": a.action_type, "target": a.target}
            for a in actions
        ],
    }

    return EscalationResult(
        actions=actions,
        audit_event=audit_event,
        side_effects=[],
    )
