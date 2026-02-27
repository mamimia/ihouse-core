#!/usr/bin/env python3
"""
Deterministic Booking Conflict Resolver
IHOUSE_SKILL_VERSION: 2026-02-26-r1

Pure function:
Reads JSON from stdin
Writes JSON to stdout
No implicit time
No storage
No network
No randomness

Typing strategy:
Make strict analyzers happy:
- All dicts explicitly typed
- No variables used outside guaranteed assignment
- No Optional outputs and no None literals in output payloads
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Set, cast


def _overlap(a_start: str, a_end: str, b_start: str, b_end: str) -> bool:
    # End equals start is NOT overlap
    return (a_start < b_end) and (a_end > b_start)


def _as_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return cast(Dict[str, Any], v)
    return cast(Dict[str, Any], {})


def _as_list(v: Any) -> List[Any]:
    if isinstance(v, list):
        return v
    return []


def main() -> int:
    # 1) Read JSON
    try:
        payload_any: Any = json.load(sys.stdin)
    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_NOT_JSON"}))
        return 2

    if not isinstance(payload_any, dict):
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID"}))
        return 2

    p: Dict[str, Any] = cast(Dict[str, Any], payload_any)

    # 2) Parse required inputs with guaranteed assignment
    req_id: str = ""
    now_utc: str = ""
    actor: Dict[str, Any] = cast(Dict[str, Any], {})
    policy: Dict[str, Any] = cast(Dict[str, Any], {})
    cand: Dict[str, Any] = cast(Dict[str, Any], {})
    existing: List[Any] = []

    booking_id: str = ""
    prop_id: str = ""
    start: str = ""
    end: str = ""
    requested_status: str = ""

    try:
        idempotency = _as_dict(p.get("idempotency"))
        time_obj = _as_dict(p.get("time"))

        req_id = str(idempotency["request_id"])
        now_utc = str(time_obj["now_utc"])

        actor = _as_dict(p.get("actor"))
        policy = _as_dict(p.get("policy"))

        cand = _as_dict(p.get("booking_candidate"))
        existing = _as_list(p.get("existing_bookings"))

        booking_id = str(cand.get("booking_id", ""))
        prop_id = str(cand["property_id"])
        start = str(cand["start_utc"])
        end = str(cand["end_utc"])

        rs_raw = cand.get("requested_status")
        requested_status = str(rs_raw) if rs_raw is not None else ""
    except Exception:
        sys.stdout.write(json.dumps({"error": "INPUT_INVALID"}))
        return 2

    # 3) Prepare audit (always emitted)
    audit: Dict[str, Any] = {
        "event_type": "AuditEvent",
        "request_id": req_id,
        "now_utc": now_utc,
        "actor_id": actor.get("actor_id"),
        "role": actor.get("role"),
        "entity_type": "booking",
        "entity_id": booking_id,
        "action": "booking_conflict_resolve",
        "candidate": {"property_id": prop_id, "start_utc": start, "end_utc": end},
        "conflicts_found": [],
        "enforced_status": "",
        "artifacts": [],
        "denial_code": "",
    }

    # 4) Validate window
    if not (start < end):
        audit["denial_code"] = "INVALID_WINDOW"
        out_invalid: Dict[str, Any] = {
            "decision": {
                "allowed": False,
                "enforced_status": "",
                "conflicts_found": [],
                "denial_code": "INVALID_WINDOW",
            },
            "artifacts_to_create": [],
            "events_to_emit": [audit],
            "side_effects": [],
        }
        sys.stdout.write(json.dumps(out_invalid))
        return 0

    # 5) Build blocking status set
    statuses_blocking_raw = policy.get("statuses_blocking", [])
    statuses_blocking_list = _as_list(statuses_blocking_raw)
    blocking: Set[str] = set(str(x) for x in statuses_blocking_list)

    # 6) Compute conflicts
    conflicts: List[str] = []

    for b_any in existing:
        if not isinstance(b_any, dict):
            continue
        b: Dict[str, Any] = cast(Dict[str, Any], b_any)

        try:
            if str(b.get("property_id", "")) != prop_id:
                continue

            if blocking:
                if str(b.get("status", "")) not in blocking:
                    continue

            b_start = str(b.get("start_utc", ""))
            b_end = str(b.get("end_utc", ""))
            if not b_start or not b_end:
                continue

            if _overlap(start, end, b_start, b_end):
                conflicts.append(str(b.get("booking_id", "")))
        except Exception:
            continue

    # 7) Decide + artifacts
    artifacts: List[Dict[str, Any]] = []
    enforced_status: str = requested_status

    if conflicts:
        enforced_status = "PendingResolution"

        artifacts.append({
            "artifact_type": "ConflictTask",
            "type_id": policy.get("conflict_task_type_id"),
            "status": "Open",
            "priority": "High",
            "property_id": prop_id,
            "booking_id": booking_id,
            "conflicts_found": conflicts,
            "request_id": req_id,
        })

        allow_override = bool(policy.get("allow_admin_override", False))
        role = str(actor.get("role", ""))

        if allow_override and role in {"admin", "ops_admin"}:
            artifacts.append({
                "artifact_type": "OverrideRequest",
                "type_id": policy.get("override_request_type_id"),
                "status": "Requested",
                "required_approver_role": "admin",
                "property_id": prop_id,
                "booking_id": booking_id,
                "conflicts_found": conflicts,
                "request_id": req_id,
            })

    # 8) Finalize audit + output
    audit["conflicts_found"] = conflicts
    audit["enforced_status"] = enforced_status
    audit["artifacts"] = [{"artifact_type": a.get("artifact_type", "")} for a in artifacts]

    out_ok: Dict[str, Any] = {
        "decision": {
            "allowed": True,
            "enforced_status": enforced_status,
            "conflicts_found": conflicts,
            "denial_code": "",
        },
        "artifacts_to_create": artifacts,
        "events_to_emit": [audit],
        "side_effects": [],
    }

    sys.stdout.write(json.dumps(out_ok))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
    