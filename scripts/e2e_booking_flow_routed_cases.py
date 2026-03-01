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


def _assert_ok(step: str, rc: int, out: Dict[str, Any], err: str) -> None:
    if err:
        print(step + "_STDERR", err)
    if rc != 0 or out.get("ok") is not True:
        print(step + "_FAIL")
        print(_pp(out))
        raise SystemExit(2)


def _sync(request_id: str, actor: Dict[str, str]) -> Dict[str, Any]:
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

    rc, out, err = _run_event(env_sync)
    _assert_ok("SYNC", rc, out, err)

    res = out.get("result") or {}
    if not isinstance(res, dict) or res.get("error"):
        print("SYNC_SKILL_ERROR", _pp(res))
        raise SystemExit(3)

    return res


def _conflict(request_id: str, actor: Dict[str, str], booking_id: str, make_conflict: bool) -> List[str]:
    existing: List[Dict[str, Any]] = []
    if make_conflict:
        existing = [
            {
                "booking_id": "b_existing_1",
                "property_id": "p1",
                "start_utc": "2026-03-04T00:00:00Z",
                "end_utc": "2026-03-06T00:00:00Z",
                "status": "confirmed",
            }
        ]

    env_conflict: Dict[str, Any] = {
        "kind": "BOOKING_CONFLICT",
        "idempotency": {"request_id": request_id + "_conflict"},
        "actor": actor,
        "payload": {
            "idempotency": {"request_id": request_id + "_conflict_inner"},
            "time": {"now_utc": "2026-02-28T12:00:00Z"},
            "actor": {"actor_id": actor["actor_id"], "role": actor["role"]},
            "policy": {
                "statuses_blocking": ["confirmed", "pending"],
                "conflict_task_type_id": "task_conflict",
                "override_request_type_id": "task_override",
                "allow_admin_override": True,
            },
            "booking_candidate": {
                "booking_id": booking_id,
                "property_id": "p1",
                "start_utc": "2026-03-01T12:00:00Z",
                "end_utc": "2026-03-05T10:00:00Z",
                "requested_status": "confirmed",
            },
            "existing_bookings": existing,
        },
    }

    rc, out, err = _run_event(env_conflict)
    _assert_ok("CONFLICT", rc, out, err)

    res = out.get("result") or {}
    if not isinstance(res, dict) or res.get("error"):
        print("CONFLICT_SKILL_ERROR", _pp(res))
        raise SystemExit(4)

    decision = res.get("decision") or {}
    conflicts = list(decision.get("conflicts_found") or [])
    return [str(x) for x in conflicts]


def _state(request_id: str, actor: Dict[str, str], booking_id: str, conflicts: List[str]) -> str:
    requested_state = "PENDING_RESOLUTION" if conflicts else "CONFIRMED"

    env_state: Dict[str, Any] = {
        "kind": "STATE_TRANSITION",
        "idempotency": {"request_id": request_id + "_state"},
        "actor": actor,
        "payload": {
            "actor": {"actor_id": actor["actor_id"], "role": actor["role"]},
            "entity": {"entity_type": "booking", "entity_id": booking_id},
            "current": {"current_state": "PENDING", "current_version": 1},
            "requested": {
                "requested_state": requested_state,
                "reason_code": "E2E_ROUTED_CASES",
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
            "time": {"now_utc": "2026-02-28T12:00:00Z"},
        },
    }

    rc, out, err = _run_event(env_state)
    _assert_ok("STATE", rc, out, err)

    res = out.get("result") or {}
    if not isinstance(res, dict) or res.get("error"):
        print("STATE_SKILL_ERROR", _pp(res))
        raise SystemExit(5)

    dec = res.get("decision") or {}
    return str(dec.get("allowed_next_state", ""))


def _run_case(name: str, make_conflict: bool) -> None:
    print("CASE", name)
    actor = {"actor_id": "u1", "role": "ops"}
    request_id = "e2e_cases_" + name

    sync_res = _sync(request_id, actor)
    booking_record = sync_res.get("booking_record") or {}
    booking_id = str(booking_record.get("booking_id", "b_airbnb_ext123"))

    conflicts = _conflict(request_id, actor, booking_id, make_conflict)
    next_state = _state(request_id, actor, booking_id, conflicts)

    expected = "PENDING_RESOLUTION" if make_conflict else "CONFIRMED"
    ok = (next_state == expected)

    print("RESULT_NEXT_STATE", next_state)
    print("EXPECTED_NEXT_STATE", expected)
    print("CASE_OK" if ok else "CASE_FAIL")
    if not ok:
        raise SystemExit(6)


def main() -> int:
    _run_case("with_conflict", True)
    _run_case("no_conflict", False)
    print("E2E_CASES_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
