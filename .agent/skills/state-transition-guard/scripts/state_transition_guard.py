#!/usr/bin/env python3
"""
Deterministic State Transition Guard

Pure function:
No implicit time
No storage
No network
No randomness

Typing strategy:
No Optional fields and no None literals to keep strict analyzers quiet.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class Decision:
    allowed: bool
    allowed_next_state: str
    denial_code: str
    applied_rules: List[str]


def _get(d: Dict[str, Any], path: Tuple[str, ...]) -> Any:
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            raise KeyError("missing:" + ".".join(path))
        cur = cur[p]
    return cur


def _build_audit(payload: Dict[str, Any]) -> Dict[str, Any]:
    current_state = str(_get(payload, ("current", "current_state")))
    requested_state = str(_get(payload, ("requested", "requested_state")))
    return {
        "event_type": "AuditEvent",
        "request_id": str(_get(payload, ("requested", "request_id"))),
        "actor_id": str(_get(payload, ("actor", "actor_id"))),
        "role": str(_get(payload, ("actor", "role"))),
        "entity_type": str(_get(payload, ("entity", "entity_type"))),
        "entity_id": str(_get(payload, ("entity", "entity_id"))),
        "current_state": current_state,
        "requested_state": requested_state,
        "allowed_next_state": current_state,
        "decision_allowed": False,
        "denial_code": "",
        "applied_rules": [],
        "now_utc": str(_get(payload, ("time", "now_utc"))),
    }


def _evaluate_priority_rules(payload: Dict[str, Any]) -> Decision:
    current_state = str(_get(payload, ("current", "current_state")))
    requested_state = str(_get(payload, ("requested", "requested_state")))
    priority_stack = _get(payload, ("context", "priority_stack"))

    if not isinstance(priority_stack, list):
        return Decision(False, current_state, "INPUT_INVALID", [])

    applied: List[str] = []
    forced_next: str = ""
    has_forced_next = False
    saw_allow = False

    for rule_set in priority_stack:
        if not isinstance(rule_set, dict):
            continue
        rules = rule_set.get("rules", [])
        if not isinstance(rules, list):
            continue

        for r in rules:
            if not isinstance(r, dict):
                continue

            rid = str(r.get("id", "rule"))
            match = r.get("match", {})
            if not isinstance(match, dict):
                continue

            if str(match.get("from")) != current_state:
                continue
            if str(match.get("to")) != requested_state:
                continue

            applied.append(rid)

            effect = r.get("effect", {})
            if not isinstance(effect, dict):
                continue

            terminal = bool(effect.get("terminal", True))
            action = str(effect.get("action", "")).lower()

            if action == "deny" and terminal:
                denial_code = str(effect.get("denial_code", "DENIED"))
                return Decision(False, current_state, denial_code, applied)

            if action == "allow":
                saw_allow = True
                if "force_next_state" in effect:
                    forced_next = str(effect["force_next_state"])
                    has_forced_next = True

                if terminal:
                    next_state = forced_next if has_forced_next else requested_state
                    return Decision(True, next_state, "", applied)

    if saw_allow:
        next_state = forced_next if has_forced_next else requested_state
        return Decision(True, next_state, "", applied)

    return Decision(False, current_state, "UNKNOWN_TRANSITION", applied)


def _check_invariants(payload: Dict[str, Any], decision: Decision) -> Decision:
    if not decision.allowed:
        return decision

    invariants = payload.get("context", {}).get("invariants")
    if invariants is None:
        return decision
    if not isinstance(invariants, list):
        return decision

    current_state = str(_get(payload, ("current", "current_state")))

    for inv in invariants:
        if not isinstance(inv, dict):
            continue
        ok = bool(inv.get("ok", True))
        if ok:
            continue

        denial_code = str(inv.get("denial_code", "INVARIANT_FAILED"))
        return Decision(False, current_state, denial_code, decision.applied_rules)

    return decision


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_NOT_JSON"}))
        return 2

    response: Dict[str, Any] = {
        "decision": None,
        "events_to_emit": [],
        "side_effects": [],
    }

    try:
        audit = _build_audit(payload)
    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID"}))
        return 2

    response["events_to_emit"].append(audit)

    try:
        decision = _evaluate_priority_rules(payload)
        decision = _check_invariants(payload, decision)
    except Exception:
        audit["denial_code"] = "RULE_CONFLICT"
        audit["decision_allowed"] = False
        response["decision"] = {
            "allowed": False,
            "allowed_next_state": audit["current_state"],
            "denial_code": "RULE_CONFLICT",
            "applied_rules": [],
        }
        sys.stdout.write(json.dumps(response))
        return 0

    audit["allowed_next_state"] = decision.allowed_next_state
    audit["decision_allowed"] = decision.allowed
    audit["denial_code"] = decision.denial_code
    audit["applied_rules"] = decision.applied_rules

    response["decision"] = {
        "allowed": decision.allowed,
        "allowed_next_state": decision.allowed_next_state,
        "denial_code": decision.denial_code,
        "applied_rules": decision.applied_rules,
    }

    sys.stdout.write(json.dumps(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())