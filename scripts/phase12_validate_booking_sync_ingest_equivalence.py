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
        raise SystemExit(f"MISMATCH {label}\n--- runner ---\n{a}\n--- legacy ---\n{b}\n")


def main() -> int:
    skill = "booking-sync-ingest"
    legacy_script = REPO / ".agent/skills/booking-sync-ingest/scripts/booking_sync_ingest.py"

    cases: List[Dict[str, Any]] = []

    # Case 1: upsert confirmed
    cases.append({
        "provider": "airbnb",
        "external_booking_id": "ext123",
        "property_id": "p1",
        "provider_payload": {
            "status": "confirmed",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
            "guest_name": "John Doe",
        },
    })

    # Case 2: cancel
    cases.append({
        "provider": "booking",
        "external_booking_id": "bkg777",
        "property_id": "p2",
        "provider_payload": {
            "status": "cancelled",
            "guest_name": "Jane",
        },
    })

    for i, payload in enumerate(cases, start=1):
        out_runner = run_runner(skill, payload)
        out_legacy = run_legacy(legacy_script, payload)
        assert_equal(f"case_{i}", out_runner, out_legacy)

    print("EQUIVALENCE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
