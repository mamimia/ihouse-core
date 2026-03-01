from __future__ import annotations

from typing import Any, Dict, List, Set, cast


# Ported from legacy:
# .agent/skills/task-completion-validator/scripts/task_completion_validator.py
# Deterministic. No IO. run(payload) returns dict.


def _as_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return cast(Dict[str, Any], v)
    return cast(Dict[str, Any], {})


def _as_list(v: Any) -> List[Any]:
    if isinstance(v, list):
        return v
    return []


def _is_nonempty(s: Any) -> bool:
    return isinstance(s, str) and len(s.strip()) > 0


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        p: Dict[str, Any] = cast(Dict[str, Any], payload)

        try:
            req_id = str(_as_dict(p.get("idempotency"))["request_id"])
            actor = _as_dict(p.get("actor"))
            ctx = _as_dict(p.get("context"))
            timers = _as_dict(ctx.get("timers_utc"))
            task = _as_dict(p.get("task"))
            policy = _as_dict(p.get("policy"))

            run_id = str(ctx.get("run_id", ""))
            now_utc = str(timers["now_utc"])
            ack_due_utc_raw = timers.get("task_ack_due_utc", "")
            completed_due_utc_raw = timers.get("task_completed_due_utc", "")

            task_id = str(task.get("task_id", ""))
            prop_id = str(task.get("property_id", ""))
            task_type = str(task.get("task_type", ""))
            state = str(task.get("state", ""))
            priority = str(task.get("priority", ""))
            ack_state = str(task.get("ack_state", ""))
        except Exception:
            return {"error": "INPUT_INVALID"}

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

        # Terminal states: no escalations
        if state in {"Completed", "Cancelled"}:
            audit_terminal: Dict[str, Any] = {
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
                    "task_ack_due_utc": str(ack_due_utc_raw or ""),
                    "task_completed_due_utc": str(completed_due_utc_raw or ""),
                },
                "triggers_fired": [],
                "actions_emitted": [],
            }
            return {"actions": [], "events_to_emit": [audit_terminal], "side_effects": []}

        ack_due_utc = str(ack_due_utc_raw or "")
        if ack_state == "Unacked" and _is_nonempty(ack_due_utc) and now_utc >= ack_due_utc:
            triggers.append("ACK_SLA_BREACH")
            if "ACK_SLA_BREACH" in notify_ops_on:
                emit("notify_ops", "ops", "ACK_SLA_BREACH")
            if "ACK_SLA_BREACH" in notify_admin_on:
                emit("notify_admin", "admin", "ACK_SLA_BREACH")

        completed_due_utc = str(completed_due_utc_raw or "")
        if _is_nonempty(completed_due_utc) and now_utc >= completed_due_utc and state != "Completed":
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

        return {"actions": actions, "events_to_emit": [audit], "side_effects": []}

    except Exception:
        return {"error": "INPUT_INVALID"}
