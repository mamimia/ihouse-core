#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from typing import Any, Dict


SKILL_REGISTRY: Dict[str, str] = {
    "state-transition-guard":
        ".agent/skills/state-transition-guard/scripts/state_transition_guard.py",
    "booking-conflict-resolver":
        ".agent/skills/booking-conflict-resolver/scripts/booking_conflict_resolver.py",
    "task-completion-validator":
        ".agent/skills/task-completion-validator/scripts/task_completion_validator.py",
    "sla-escalation-engine":
        ".agent/skills/sla-escalation-engine/scripts/sla_escalation_engine.py",
}


class SkillExecutionError(Exception):
    pass


def _json_error(error: str, **extra: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {"error": error}
    for k, v in extra.items():
        out[k] = v
    return out


def run_skill(skill_name: str, skill_input: Dict[str, Any]) -> Dict[str, Any]:
    if skill_name not in SKILL_REGISTRY:
        raise SkillExecutionError(f"Unknown skill: {skill_name}")

    script_path = SKILL_REGISTRY[skill_name]

    p = subprocess.Popen(
        ["python3", script_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stdout, stderr = p.communicate(input=json.dumps(skill_input))

    if p.returncode != 0:
        raise SkillExecutionError(
            f"Skill failed ({skill_name})\nSTDERR:\n{stderr}\nSTDOUT:\n{stdout}"
        )

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        raise SkillExecutionError(
            f"Skill returned invalid JSON ({skill_name})\n{stdout}"
        )


def main() -> int:
    if len(sys.argv) != 2:
        sys.stdout.write(json.dumps(_json_error("USAGE", usage="skill_runner.py <skill_name>")))
        return 2

    skill_name = sys.argv[1]

    try:
        envelope: Dict[str, Any] = json.load(sys.stdin)
    except Exception:
        sys.stdout.write(json.dumps(_json_error("INPUT_NOT_JSON")))
        return 2

    actor = envelope.get("actor")
    if not isinstance(actor, dict) or not actor.get("actor_id") or not actor.get("role"):
        sys.stdout.write(json.dumps(_json_error("INPUT_INVALID", missing=["actor.actor_id", "actor.role"])))
        return 2

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        sys.stdout.write(json.dumps(_json_error("INPUT_INVALID", missing=["payload (object)"])))
        return 2

    try:
        out = run_skill(skill_name, payload)
        sys.stdout.write(json.dumps(out))
        return 0
    except SkillExecutionError as e:
        sys.stdout.write(json.dumps(_json_error("SKILL_EXECUTION_ERROR", message=str(e))))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())