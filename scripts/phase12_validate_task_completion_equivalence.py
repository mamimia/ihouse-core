#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


REPO = Path(__file__).resolve().parents[1]


def _canon_json(text: str) -> str:
    obj = json.loads(text)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def run_runner(skill: str, payload: Dict[str, Any]) -> str:
    env = {
        "kind": "manual-test",
        "idempotency": {"request_id": "req-manual"},
        "actor": {"actor_id": "u1", "role": "admin"},
        "payload": payload,
    }
    p = subprocess.run(
        ["python3", str(REPO / ".agent/system/skill_runner.py"), skill],
        input=json.dumps(env),
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        raise SystemExit(f"RUNNER_FAILED rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return _canon_json(p.stdout)


def run_legacy(script_path: Path, payload: Dict[str, Any]) -> str:
    p = subprocess.run(
        ["python3", str(script_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        raise SystemExit(f"LEGACY_FAILED rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return _canon_json(p.stdout)


def assert_equal(label: str, a: str, b: str) -> None:
    if a != b:
        raise SystemExit(
            f"MISMATCH {label}\n--- runner ---\n{a}\n--- legacy ---\n{b}\n"
        )


def main() -> int:
    skill = "task-completion-validator"
    legacy_script = REPO / ".agent/skills/task-completion-validator/scripts/task_completion_validator.py"

    base_policy = {
        "notify_ops_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
        "notify_admin_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
    }
    base_actor = {"actor_id": "u1", "role": "ops"}

    cases: List[Dict[str, Any]] = []

    # Case 1: ACK overdue -> ACK_SLA_BREACH + two actions (ops+admin)
    cases.append({
        "idempotency": {"request_id": "r1"},
        "actor": base_actor,
        "context": {
            "run_id": "run1",
            "timers_utc": {
                "now_utc": "2026-02-28T12:00:00Z",
                "task_ack_due_utc": "2026-02-28T11:00:00Z",
                "task_completed_due_utc": "2026-02-28T13:00:00Z",
            }
        },
        "task": {
            "task_id": "t1",
            "property_id": "p1",
            "task_type": "cleaning",
            "state": "Open",
            "priority": "Normal",
            "ack_state": "Unacked",
        },
        "policy": base_policy,
    })

    # Case 2: completion overdue -> COMPLETION_SLA_BREACH + two actions (ops+admin)
    cases.append({
        "idempotency": {"request_id": "r2"},
        "actor": base_actor,
        "context": {
            "run_id": "run2",
            "timers_utc": {
                "now_utc": "2026-02-28T14:00:00Z",
                "task_ack_due_utc": "2026-02-28T15:00:00Z",
                "task_completed_due_utc": "2026-02-28T13:00:00Z",
            }
        },
        "task": {
            "task_id": "t2",
            "property_id": "p1",
            "task_type": "cleaning",
            "state": "InProgress",
            "priority": "Normal",
            "ack_state": "Acked",
        },
        "policy": base_policy,
    })

    # Case 3: terminal state -> no triggers/actions
    cases.append({
        "idempotency": {"request_id": "r3"},
        "actor": base_actor,
        "context": {
            "run_id": "run3",
            "timers_utc": {
                "now_utc": "2026-02-28T14:00:00Z",
                "task_ack_due_utc": "2026-02-28T11:00:00Z",
                "task_completed_due_utc": "2026-02-28T13:00:00Z",
            }
        },
        "task": {
            "task_id": "t3",
            "property_id": "p1",
            "task_type": "cleaning",
            "state": "Completed",
            "priority": "Normal",
            "ack_state": "Acked",
        },
        "policy": base_policy,
    })

    for i, payload in enumerate(cases, start=1):
        out_runner = run_runner(skill, payload)
        out_legacy = run_legacy(legacy_script, payload)
        assert_equal(f"case_{i}", out_runner, out_legacy)

    print("EQUIVALENCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
