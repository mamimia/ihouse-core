#!/usr/bin/env python3
"""
Deterministic SLA Escalation Engine
IHOUSE_SKILL_VERSION: 2026-02-26-r2

Pure function:
Reads JSON from stdin
Writes JSON to stdout
No implicit time
No storage
No network
No randomness
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Set, cast


def _as_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return cast(Dict[str, Any], v)
    return cast(Dict[str, Any], {})


def _as_list(v: Any) -> List[Any]:
    if isinstance(v, list):
        return v
    return []


def _is_nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and len(v.strip()) > 0


def main() -> int:
    try:
        payload_any: Any = json.load(sys.stdin)
    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_NOT_JSON"}))
        return 2

    if not isinstance(payload_any, dict):
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID"}))
        return 2

    p: Dict[str, Any] = cast(Dict[str, Any], payload_any)

    try:
        req_id = str(_as_dict(p.get("idempotency"))["request_id"])
        actor = _as_dict(p.get("actor"))
        ctx = _as_dict(p.get("context"))
        timers = _as_dict(ctx.get("timers_utc"))
        task = _as_dict(p.get("task"))
        policy = _as_dict(p.get("policy"))

        run_id = str(ctx.get("run_id", ""))

        now_utc = str(timers["now_utc"])
        ack_due_utc = str(timers.get("task_ack_due_utc", "") or "")
        completed_due_utc = str(timers.get("task_completed_due_utc", "") or "")

        task_id = str(task.get("task_id", ""))
        prop_id = str(task.get("property_id", ""))
        task_type = str(task.get("task_type", ""))
        state = str(task.get("state", ""))
        priority = str(task.get("priority", ""))
        ack_state = str(task.get("ack_state", ""))

    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID"}))
        return 2

    notify_ops_on: Set[str] = set(str(x) for x in _as_list(policy.get("notify_ops_on")))
    notify_admin_on: Set[str] = set(str(x) for x in _as_list(policy.get("notify_admin_on")))

    triggers: List[str] = []
    actions: List[Dict[str, Any]] = []

    def emit(action_type: str, target: str, reason: str) -> None:
        actions.append(
            {
                "action_type": action_type,
                "target": target,
                "reason": reason,
                "task_id": task_id,
                "property_id": prop_id,
                "request_id": req_id,
            }
        )

    terminal = state in {"Completed", "Cancelled"}
    if not terminal:
        if ack_state == "Unacked" and _is_nonempty_str(ack_due_utc) and now_utc >= ack_due_utc:
            triggers.append("ACK_SLA_BREACH")
            if "ACK_SLA_BREACH" in notify_ops_on:
                emit("notify_ops", "ops", "ACK_SLA_BREACH")
            if "ACK_SLA_BREACH" in notify_admin_on:
                emit("notify_admin", "admin", "ACK_SLA_BREACH")

        if _is_nonempty_str(completed_due_utc) and now_utc >= completed_due_utc and state != "Completed":
            triggers.append("COMPLETION_SLA_BREACH")
            if "COMPLETION_SLA_BREACH" in notify_ops_on:
                emit("notify_ops", "ops", "COMPLETION_SLA_BREACH")
            if "COMPLETION_SLA_BREACH" in notify_admin_on:
                emit("notify_admin", "admin", "COMPLETION_SLA_BREACH")

    audit: Dict[str, Any] = {
        "event_type": "AuditEvent",
        "request_id": req_id,
        "run_id": run_id,
        "now_utc": now_utc,
        "actor_id": actor.get("actor_id"),
        "role": actor.get("role"),
        "task": {
            "task_id": task_id,
            "property_id": prop_id,
            "task_type": task_type,
            "state": state,
            "priority": priority,
            "ack_state": ack_state,
        },
        "timers_utc": {
            "task_ack_due_utc": ack_due_utc,
            "task_completed_due_utc": completed_due_utc,
        },
        "triggers_fired": triggers,
        "actions_emitted": [{"action_type": a["action_type"], "target": a["target"]} for a in actions],
    }

    out_ok: Dict[str, Any] = {"actions": actions, "events_to_emit": [audit], "side_effects": []}
    sys.stdout.write(json.dumps(out_ok))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())