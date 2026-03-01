#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List, Tuple


def _pp(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _run_event(envelope: Dict[str, Any]) -> Tuple[int, Dict[str, Any], str]:
    p = subprocess.run(
        ["python3", "./.agent/system/event_router.py"],
        input=json.dumps(envelope),
        text=True,
        capture_output=True,
    )
    stderr = (p.stderr or "").strip()
    try:
        out = json.loads(p.stdout) if p.stdout else {}
        if not isinstance(out, dict):
            out = {"_raw": p.stdout}
    except Exception:
        out = {"_raw": p.stdout}
    return p.returncode, out, stderr


def main() -> int:
    request_id = "e2e_routed_1"
    now_utc = "2026-02-28T12:00:00Z"
    actor = {"actor_id": "u1", "role": "ops"}

    # 1) BOOKING_SYNC_INGEST
    env_sync: Dict[str, Any] = {
        "kind": "BOOKING_SYNC_INGEST",
        "idempotency": {"request_id": request_id + "_sync"},
        "actor": actor,
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
    }

    print("STEP_1_SYNC_ENVELOPE")
    print(_pp(env_sync))
    rc, out, err = _run_event(env_sync)
    print("STEP_1_SYNC_OUTPUT")
    print(_pp(out))
    if err:
        print("STEP_1_SYNC_STDERR", err)

    if rc != 0 or out.get("ok") is not True:
        print("FLOW_ABORT sync_router_fail")
        return 2

    res = out.get("result") or {}
    if not isinstance(res, dict) or res.get("error"):
        print("FLOW_ABORT sync_skill_error")
        return 3

    booking_record = res.get("booking_record") or {}
    booking_id = str(booking_record.get("booking_id", ""))
    property_id = str(booking_record.get("property_id", ""))

    # 2) BOOKING_CONFLICT
    env_conflict: Dict[str, Any] = {
        "kind": "BOOKING_CONFLICT",
        "idempotency": {"request_id": request_id + "_conflict"},
        "actor": actor,
        "payload": {
            "idempotency": {"request_id": request_id + "_conflict_inner"},
            "time": {"now_utc": now_utc},
            "actor": {"actor_id": actor["actor_id"], "role": actor["role"]},
            "policy": {
                "statuses_blocking": ["confirmed", "pending"],
                "conflict_task_type_id": "task_conflict",
                "override_request_type_id": "task_override",
                "allow_admin_override": True,
            },
            "booking_candidate": {
                "booking_id": booking_id or "b_new",
                "property_id": property_id or "p1",
                "start_utc": "2026-03-01T12:00:00Z",
                "end_utc": "2026-03-05T10:00:00Z",
                "requested_status": "confirmed",
            },
            "existing_bookings": [
                {
                    "booking_id": "b_existing_1",
                    "property_id": property_id or "p1",
                    "start_utc": "2026-03-04T00:00:00Z",
                    "end_utc": "2026-03-06T00:00:00Z",
                    "status": "confirmed",
                }
            ],
        },
    }

    print("STEP_2_CONFLICT_ENVELOPE")
    print(_pp(env_conflict))
    rc, out, err = _run_event(env_conflict)
    print("STEP_2_CONFLICT_OUTPUT")
    print(_pp(out))
    if err:
        print("STEP_2_CONFLICT_STDERR", err)

    if rc != 0 or out.get("ok") is not True:
        print("FLOW_ABORT conflict_router_fail")
        return 4

    res = out.get("result") or {}
    if not isinstance(res, dict) or res.get("error"):
        print("FLOW_ABORT conflict_skill_error")
        return 5

    decision = res.get("decision") or {}
    conflicts: List[str] = list(decision.get("conflicts_found") or [])

    # 3) STATE_TRANSITION
    requested_state = "PENDING_RESOLUTION" if conflicts else "CONFIRMED"

    env_state: Dict[str, Any] = {
        "kind": "STATE_TRANSITION",
        "idempotency": {"request_id": request_id + "_state"},
        "actor": actor,
        "payload": {
            "actor": {"actor_id": actor["actor_id"], "role": actor["role"]},
            "entity": {"entity_type": "booking", "entity_id": booking_id or "b_new"},
            "current": {"current_state": "PENDING", "current_version": 1},
            "requested": {
                "requested_state": requested_state,
                "reason_code": "E2E_ROUTED_FLOW",
                "request_id": request_id + "_state_inner",
            },
            "context": {
                "priority_stack": [
                    {
                        "rules": [
                            {
                                "id": "allow_pending_to_confirmed",
                                "match": {"from": "PENDING", "to": "CONFIRMED"},
                                "effect": {"action": "allow", "terminal": True},
                            },
                            {
                                "id": "allow_pending_to_pending_resolution",
                                "match": {"from": "PENDING", "to": "PENDING_RESOLUTION"},
                                "effect": {"action": "allow", "terminal": True},
                            },
                        ]
                    }
                ],
                "invariants": [],
                "related_facts": {"conflicts_found": conflicts},
            },
            "time": {"now_utc": now_utc},
        },
    }

    print("STEP_3_STATE_ENVELOPE")
    print(_pp(env_state))
    rc, out, err = _run_event(env_state)
    print("STEP_3_STATE_OUTPUT")
    print(_pp(out))
    if err:
        print("STEP_3_STATE_STDERR", err)

    if rc != 0 or out.get("ok") is not True:
        print("FLOW_ABORT state_router_fail")
        return 6

    res = out.get("result") or {}
    if not isinstance(res, dict) or res.get("error"):
        print("FLOW_ABORT state_skill_error")
        return 7

    print("FLOW_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
