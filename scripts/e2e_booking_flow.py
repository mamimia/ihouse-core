#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

# allow importing from ./src
sys.path.insert(0, "./src")

from core.skills.booking_sync_ingest import skill as sync_skill
from core.skills.booking_conflict_resolver import skill as conflict_skill
from core.skills.state_transition_guard import skill as stg_skill


def _pp(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def main() -> int:
    request_id = "e2e_1"
    now_utc = "2026-02-28T12:00:00Z"
    actor = {"actor_id": "u1", "role": "ops"}

    print("STEP_1_SYNC_INPUT")
    sync_payload: Dict[str, Any] = {
        "provider": "airbnb",
        "external_booking_id": "ext123",
        "property_id": "p1",
        "provider_payload": {
            "status": "confirmed",
            "start_date": "2026-03-01",
            "end_date": "2026-03-05",
            "guest_name": "John Doe",
        },
    }
    print(_pp(sync_payload))

    sync_out = sync_skill.run(sync_payload)
    print("STEP_1_SYNC_OUTPUT")
    print(_pp(sync_out))

    if not isinstance(sync_out, dict) or sync_out.get("error"):
        print("FLOW_ABORT sync_error")
        return 2

    booking_record = sync_out.get("booking_record") or {}
    booking_id = str(booking_record.get("booking_id", ""))
    property_id = str(booking_record.get("property_id", ""))

    print("STEP_2_CONFLICT_INPUT")
    conflict_payload: Dict[str, Any] = {
        "idempotency": {"request_id": request_id},
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
    }
    print(_pp(conflict_payload))

    conflict_out = conflict_skill.run(conflict_payload)
    print("STEP_2_CONFLICT_OUTPUT")
    print(_pp(conflict_out))

    if not isinstance(conflict_out, dict) or conflict_out.get("error"):
        print("FLOW_ABORT conflict_error")
        return 3

    decision = conflict_out.get("decision") or {}
    conflicts: List[str] = list(decision.get("conflicts_found") or [])
    enforced_status = str(decision.get("enforced_status", ""))

    # decide target state for demo
    current_state = "PENDING"
    if conflicts:
        requested_state = "PENDING_RESOLUTION"
    else:
        requested_state = "CONFIRMED"

    print("STEP_3_STATE_TRANSITION_INPUT")
    st_payload: Dict[str, Any] = {
        "actor": {"actor_id": actor["actor_id"], "role": actor["role"]},
        "entity": {"entity_type": "booking", "entity_id": booking_id or "b_new"},
        "current": {"current_state": current_state, "current_version": 1},
        "requested": {
            "requested_state": requested_state,
            "reason_code": "E2E_FLOW",
            "request_id": request_id,
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
            "related_facts": {
                "conflicts_found": conflicts,
                "enforced_status": enforced_status,
            },
        },
        "time": {"now_utc": now_utc},
    }
    print(_pp(st_payload))

    st_out = stg_skill.run(st_payload)
    print("STEP_3_STATE_TRANSITION_OUTPUT")
    print(_pp(st_out))

    print("FLOW_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
