#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


REPO = Path(__file__).resolve().parents[1]


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
    return p.stdout.strip()


def run_legacy(script_path: Path, payload: Dict[str, Any]) -> str:
    p = subprocess.run(
        ["python3", str(script_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
    )
    if p.returncode != 0:
        raise SystemExit(f"LEGACY_FAILED rc={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}")
    return p.stdout.strip()


def assert_equal(label: str, a: str, b: str) -> None:
    if a != b:
        raise SystemExit(
            f"MISMATCH {label}\n--- runner(core/legacy switch) ---\n{a}\n--- legacy ---\n{b}\n"
        )


def main() -> int:
    if len(sys.argv) != 3:
        print("USAGE: phase12_validate_equivalence.py <skill_name> <legacy_script_path>")
        return 2

    skill = sys.argv[1]
    legacy_script = REPO / sys.argv[2]
    if not legacy_script.exists():
        print(f"LEGACY_SCRIPT_NOT_FOUND path={legacy_script}")
        return 2

    cases: list[Dict[str, Any]] = []

    if skill == "state-transition-guard":
        cases = [
            {
                "current": {"current_state": "A"},
                "requested": {"requested_state": "B", "request_id": "r1"},
                "actor": {"actor_id": "u1", "role": "admin"},
                "entity": {"entity_type": "job", "entity_id": "e1"},
                "context": {"priority_stack": [{"rules": [{"id": "allow_ab", "match": {"from": "A", "to": "B"}, "effect": {"action": "allow", "terminal": True}}]}]},
                "time": {"now_utc": "2026-02-28T00:00:00Z"},
            },
            {
                "current": {"current_state": "A"},
                "requested": {"requested_state": "B", "request_id": "r2"},
                "actor": {"actor_id": "u1", "role": "admin"},
                "entity": {"entity_type": "job", "entity_id": "e1"},
                "context": {"priority_stack": [{"rules": [{"id": "deny_ab", "match": {"from": "A", "to": "B"}, "effect": {"action": "deny", "denial_code": "NOPE", "terminal": True}}]}]},
                "time": {"now_utc": "2026-02-28T00:00:00Z"},
            },
        ]

    else:
        # Generic: user supplies payloads later if needed
        print("NO_BUILTIN_CASES")
        return 2

    for i, payload in enumerate(cases, start=1):
        out_runner = run_runner(skill, payload)
        out_legacy = run_legacy(legacy_script, payload)
        assert_equal(f"case_{i}", out_runner, out_legacy)

    print("EQUIVALENCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
