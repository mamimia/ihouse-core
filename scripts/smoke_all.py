#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List, Tuple


def _run_event(envelope: Dict[str, Any]) -> Tuple[int, str, str]:
    p = subprocess.run(
        ["python3", "./.agent/system/event_router.py"],
        input=json.dumps(envelope),
        text=True,
        capture_output=True,
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _pass(rc: int, out: str) -> bool:
    if rc != 0:
        return False
    try:
        j = json.loads(out) if out else {}
    except Exception:
        return False
    return isinstance(j, dict) and j.get("ok") is True


def main() -> int:
    cases: List[Dict[str, Any]] = []

    cases.append({
        "name": "STATE_TRANSITION",
        "env": {
            "kind": "STATE_TRANSITION",
            "idempotency": {"request_id": "smoke_st_1"},
            "actor": {"actor_id": "u1", "role": "admin"},
            "payload": {
                "current": {"current_state": "A"},
                "requested": {"requested_state": "B", "request_id": "r1"},
                "actor": {"actor_id": "u1", "role": "admin"},
                "entity": {"entity_type": "job", "entity_id": "e1"},
                "context": {"priority_stack": [{"rules": [{
                    "id": "allow_ab",
                    "match": {"from": "A", "to": "B"},
                    "effect": {"action": "allow", "terminal": True},
                }]}]},
                "time": {"now_utc": "2026-02-28T00:00:00Z"},
            },
        },
    })

    cases.append({
        "name": "BOOKING_CONFLICT",
        "env": {
            "kind": "BOOKING_CONFLICT",
            "idempotency": {"request_id": "smoke_bc_1"},
            "actor": {"actor_id": "u1", "role": "admin"},
            "payload": {
                "idempotency": {"request_id": "r1"},
                "time": {"now_utc": "2026-02-28T00:00:00Z"},
                "actor": {"actor_id": "u1", "role": "admin"},
                "policy": {
                    "statuses_blocking": ["confirmed", "pending"],
                    "conflict_task_type_id": "task_conflict",
                    "override_request_type_id": "task_override",
                    "allow_admin_override": True,
                },
                "booking_candidate": {
                    "booking_id": "b_new",
                    "property_id": "p1",
                    "start_utc": "2026-03-01T12:00:00Z",
                    "end_utc": "2026-03-05T10:00:00Z",
                    "requested_status": "confirmed",
                },
                "existing_bookings": [{
                    "booking_id": "b1",
                    "property_id": "p1",
                    "start_utc": "2026-03-04T00:00:00Z",
                    "end_utc": "2026-03-06T00:00:00Z",
                    "status": "confirmed",
                }],
            },
        },
    })

    cases.append({
        "name": "TASK_COMPLETION",
        "env": {
            "kind": "TASK_COMPLETION",
            "idempotency": {"request_id": "smoke_tc_1"},
            "actor": {"actor_id": "u1", "role": "ops"},
            "payload": {
                "idempotency": {"request_id": "r1"},
                "actor": {"actor_id": "u1", "role": "ops"},
                "context": {
                    "run_id": "run1",
                    "timers_utc": {
                        "now_utc": "2026-02-28T12:00:00Z",
                        "task_ack_due_utc": "2026-02-28T11:00:00Z",
                        "task_completed_due_utc": "2026-02-28T13:00:00Z",
                    },
                },
                "task": {
                    "task_id": "t1",
                    "property_id": "p1",
                    "task_type": "cleaning",
                    "state": "Open",
                    "priority": "Normal",
                    "ack_state": "Unacked",
                },
                "policy": {
                    "notify_ops_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
                    "notify_admin_on": ["ACK_SLA_BREACH", "COMPLETION_SLA_BREACH"],
                },
            },
        },
    })

    cases.append({
        "name": "SLA_ESCALATION",
        "env": {
            "kind": "SLA_ESCALATION",
            "idempotency": {"request_id": "smoke_sla_1"},
            "actor": {"actor_id": "u1", "role": "ops"},
            "payload": {
                "idempotency": {"request_id": "r1"},
                "actor": {"actor_id": "u1", "role": "ops"},
                "context": {
                    "run_id": "run1",
                    "timers_utc": {
                        "now_utc": "2026-02-28T12:00:00Z",
                        "task_ack_due_utc": "2026-02-28T11:00:00Z",
                        "task_completed_due_utc": "2026-02-28T13:00:00Z",
                    },
                },
                "task": {
                    "task_id": "t1",
                    "property_id": "p1",
                    "task_type": "cleaning",
                    "state": "Open",
                    "priority": "Normal",
                    "ack_state": "Unacked",
                },
                "policy": {
                    "notify_ops_on": ["ACK_SLA_BREACH"],
                    "notify_admin_on": [],
                },
            },
        },
    })

    cases.append({
        "name": "BOOKING_SYNC_INGEST",
        "env": {
            "kind": "BOOKING_SYNC_INGEST",
            "idempotency": {"request_id": "smoke_sync_1"},
            "actor": {"actor_id": "u1", "role": "ops"},
            "payload": {
                "provider": "airbnb",
                "external_booking_id": "ext123",
                "property_id": "p1",
                "provider_payload": {
                    "status": "confirmed",
                    "start_date": "2026-03-01",
                    "end_date": "2026-03-05",
                    "guest_name": "John Doe",
                },
            },
        },
    })

    ok = True
    for c in cases:
        rc, out, err = _run_event(c["env"])
        passed = _pass(rc, out)
        print(c["name"], "OK" if passed else "FAIL")
        if not passed:
            ok = False
            print("STDERR", err)
            print("OUT", out)

    # E2E routed cases (with + without conflict)
    import subprocess
    r = subprocess.run(["python3","scripts/e2e_booking_flow_routed_cases.py"], text=True, capture_output=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        ok = False
        print("E2E_ROUTED_CASES FAIL")
        print("STDERR", (r.stderr or "").strip())
    print("SMOKE_ALL_OK" if ok else "SMOKE_FAIL")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
