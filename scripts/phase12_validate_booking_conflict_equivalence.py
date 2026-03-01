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
    skill = "booking-conflict-resolver"
    legacy_script = REPO / ".agent/skills/booking-conflict-resolver/scripts/booking_conflict_resolver.py"

    cases: List[Dict[str, Any]] = []

    base_policy = {
        "statuses_blocking": ["confirmed", "pending"],
        "conflict_task_type_id": "task_conflict",
        "override_request_type_id": "task_override",
        "allow_admin_override": True,
    }
    base_actor = {"actor_id": "u1", "role": "admin"}
    base_time = {"now_utc": "2026-02-28T00:00:00Z"}

    # Case 1: overlap conflict + admin override enabled
    cases.append({
        "idempotency": {"request_id": "r1"},
        "time": base_time,
        "actor": base_actor,
        "policy": base_policy,
        "booking_candidate": {
            "booking_id": "b_new",
            "property_id": "p1",
            "start_utc": "2026-03-01T12:00:00Z",
            "end_utc": "2026-03-05T10:00:00Z",
            "requested_status": "confirmed",
        },
        "existing_bookings": [
            {
                "booking_id": "b1",
                "property_id": "p1",
                "start_utc": "2026-03-04T00:00:00Z",
                "end_utc": "2026-03-06T00:00:00Z",
                "status": "confirmed",
            }
        ],
    })

    # Case 2: no conflict (non-overlap)
    cases.append({
        "idempotency": {"request_id": "r2"},
        "time": base_time,
        "actor": base_actor,
        "policy": base_policy,
        "booking_candidate": {
            "booking_id": "b_new2",
            "property_id": "p1",
            "start_utc": "2026-03-01T12:00:00Z",
            "end_utc": "2026-03-03T10:00:00Z",
            "requested_status": "confirmed",
        },
        "existing_bookings": [
            {
                "booking_id": "b2",
                "property_id": "p1",
                "start_utc": "2026-03-03T10:00:00Z",
                "end_utc": "2026-03-05T10:00:00Z",
                "status": "confirmed",
            }
        ],
    })

    # Case 3: overlap exists but status not blocking => no conflict
    cases.append({
        "idempotency": {"request_id": "r3"},
        "time": base_time,
        "actor": base_actor,
        "policy": base_policy,
        "booking_candidate": {
            "booking_id": "b_new3",
            "property_id": "p1",
            "start_utc": "2026-03-01T12:00:00Z",
            "end_utc": "2026-03-05T10:00:00Z",
            "requested_status": "confirmed",
        },
        "existing_bookings": [
            {
                "booking_id": "b3",
                "property_id": "p1",
                "start_utc": "2026-03-04T00:00:00Z",
                "end_utc": "2026-03-06T00:00:00Z",
                "status": "cancelled",
            }
        ],
    })

    for i, payload in enumerate(cases, start=1):
        out_runner = run_runner(skill, payload)
        out_legacy = run_legacy(legacy_script, payload)
        assert_equal(f"case_{i}", out_runner, out_legacy)

    print("EQUIVALENCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
