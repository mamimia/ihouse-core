from __future__ import annotations

import json
import time
import sqlite3
from typing import Dict, Any, Optional


def _now_ms() -> int:
    return int(time.time() * 1000)


def project_event(
    conn: sqlite3.Connection,
    kind: str,
    envelope: Dict[str, Any],
    response: Dict[str, Any],
    event_id: Optional[str] = None,
    now_ms: Optional[int] = None,
) -> None:
    """
    Projects derived state into materialized tables.
    Determinism rule:
    - Live path may omit now_ms (uses wall-clock).
    - Rebuild path must pass now_ms from events.ts_ms.
    """
    if not response.get("ok"):
        return

    ts = int(now_ms) if now_ms is not None else _now_ms()

    if kind == "BOOKING_CONFLICT":
        _project_booking_conflict(conn, envelope, response, ts)

    if kind in ("TASK_COMPLETION", "SLA_ESCALATION"):
        _project_notifications(conn, kind, response, ts)
        _project_outbox_from_notifications(conn, kind, response, event_id, ts)

    if kind == "BOOKING_SYNC_INGEST":
        _project_booking_sync_ingest(conn, envelope, response, ts)


def _project_booking_sync_ingest(
    conn: sqlite3.Connection,
    envelope: Dict[str, Any],
    response: Dict[str, Any],
    now_ms: int,
) -> None:
    result = response.get("result", {})
    decision = result.get("decision") or {}
    action = decision.get("action")

    rec = result.get("booking_record") or {}
    booking_id = rec.get("booking_id")
    property_id = rec.get("property_id")

    if not booking_id or not property_id:
        return

    # Domain write happens ONLY via projection of a persisted event.
    # Uses deterministic now_ms passed from event timestamp on rebuild.
    with conn:
        if action == "cancel":
            conn.execute(
                """
                UPDATE bookings
                SET status = ?, updated_at_ms = ?
                WHERE booking_id = ?
                """,
                ("cancelled", now_ms, booking_id),
            )
            return

        if action == "upsert":
            start_date = rec.get("start_date")
            end_date = rec.get("end_date")
            status = rec.get("status") or "confirmed"
            guest_name = rec.get("guest_name")
            external_ref = rec.get("external_ref")

            if not start_date or not end_date:
                return

            # Preserve created_at_ms if booking already exists.
            row = conn.execute(
                "SELECT created_at_ms FROM bookings WHERE booking_id = ?",
                (booking_id,),
            ).fetchone()
            created_at_ms = int(row["created_at_ms"]) if row is not None else now_ms

            conn.execute(
                """
                INSERT OR REPLACE INTO bookings(
                    booking_id,
                    property_id,
                    external_ref,
                    start_date,
                    end_date,
                    status,
                    guest_name,
                    created_at_ms,
                    updated_at_ms
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    booking_id,
                    property_id,
                    external_ref,
                    start_date,
                    end_date,
                    status,
                    guest_name,
                    created_at_ms,
                    now_ms,
                ),
            )


def _project_booking_conflict(
    conn: sqlite3.Connection,
    envelope: Dict[str, Any],
    response: Dict[str, Any],
    now_ms: int,
) -> None:
    result = response.get("result", {})
    artifacts = result.get("artifacts_to_create", [])

    request_id = response.get("request_id")

    with conn:
        for art in artifacts:
            if art.get("artifact_type") == "ConflictTask":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO conflict_tasks(
                        conflict_task_id,
                        booking_id,
                        property_id,
                        status,
                        priority,
                        conflicts_json,
                        request_id,
                        created_at_ms,
                        updated_at_ms
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"conflict_{art.get('booking_id')}_{request_id}",
                        art.get("booking_id"),
                        art.get("property_id"),
                        art.get("status"),
                        art.get("priority"),
                        json.dumps(art.get("conflicts_found", [])),
                        request_id,
                        now_ms,
                        now_ms,
                    ),
                )

            if art.get("artifact_type") == "OverrideRequest":
                conn.execute(
                    """
                    INSERT OR REPLACE INTO booking_overrides(
                        override_id,
                        booking_id,
                        property_id,
                        status,
                        required_approver_role,
                        conflicts_json,
                        request_id,
                        created_at_ms,
                        updated_at_ms
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"override_{art.get('booking_id')}_{request_id}",
                        art.get("booking_id"),
                        art.get("property_id"),
                        art.get("status"),
                        art.get("required_approver_role"),
                        json.dumps(art.get("conflicts_found", [])),
                        request_id,
                        now_ms,
                        now_ms,
                    ),
                )

        # If conflict resolver enforced a status, reflect it back into bookings
        try:
            decision = result.get("decision", {}) if isinstance(result, dict) else {}
            enforced_status = decision.get("enforced_status")
            booking_id_to_update = None

            if artifacts:
                first = artifacts[0] if isinstance(artifacts[0], dict) else {}
                booking_id_to_update = first.get("booking_id")

            if enforced_status and booking_id_to_update:
                candidate = (envelope.get("payload") or {}).get("booking_candidate") or {}
                cand_bid = str(candidate.get("booking_id") or "")
                cand_pid = str(candidate.get("property_id") or "")
                start_utc = str(candidate.get("start_utc") or "")
                end_utc = str(candidate.get("end_utc") or "")
                start_date = start_utc[:10] if len(start_utc) >= 10 else None
                end_date = end_utc[:10] if len(end_utc) >= 10 else None

                status = str(enforced_status)
                if status == "PendingResolution":
                    status = "PendingResolution"
                else:
                    status = status.lower()

                # FK: bookings.property_id -> properties.property_id

                if cand_pid:
                    conn.execute(
                        "INSERT OR IGNORE INTO properties(property_id, name, status, created_at_ms, updated_at_ms) VALUES(?, ?, 'active', ?, ?)",
                        (cand_pid, cand_pid, now_ms, now_ms),
                    )

                # Ensure booking exists so OPEN conflict task never points to a missing booking
                if cand_bid and cand_pid and start_date and end_date:
                    conn.execute(
                        "INSERT OR IGNORE INTO bookings(booking_id, property_id, external_ref, start_date, end_date, status, guest_name, created_at_ms, updated_at_ms) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (cand_bid, cand_pid, None, start_date, end_date, status, None, now_ms, now_ms),
                    )

                conn.execute(
                    "UPDATE bookings SET status = ?, updated_at_ms = ? WHERE booking_id = ?",
                    (status, now_ms, str(booking_id_to_update)),
                )
        except Exception as e:
            import sys
            print(f"BOOKING_CONFLICT_ENFORCED_STATUS_ERROR: {e!r}", file=sys.stderr)
            raise


def _project_notifications(
    conn: sqlite3.Connection,
    kind: str,
    response: Dict[str, Any],
    now_ms: int,
) -> None:
    result = response.get("result", {})
    actions = result.get("actions", [])

    request_id = response.get("request_id")

    with conn:
        for idx, act in enumerate(actions):
            conn.execute(
                """
                INSERT OR REPLACE INTO notifications(
                    notification_id,
                    request_id,
                    kind,
                    action_type,
                    target,
                    reason,
                    property_id,
                    task_id,
                    created_at_ms
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"{kind}_{request_id}_{idx}",
                    request_id,
                    kind,
                    act.get("action_type"),
                    act.get("target"),
                    act.get("reason"),
                    act.get("property_id"),
                    act.get("task_id"),
                    now_ms,
                ),
            )

def _stable_outbox_id(event_id: str, channel: str, action_type: str, target: Optional[str]) -> str:
    t = target or ""
    return f"outbox_{event_id}_{channel}_{action_type}_{t}"


def _project_outbox_from_notifications(
    conn: sqlite3.Connection,
    kind: str,
    response: Dict[str, Any],
    event_id: Optional[str],
    now_ms: int,
) -> None:
    if not event_id:
        return

    result = response.get("result", {})
    actions = result.get("actions", [])
    if not isinstance(actions, list) or not actions:
        return

    request_id = response.get("request_id")

    with conn:
        for act in actions:
            if not isinstance(act, dict):
                continue

            action_type = str(act.get("action_type") or "")
            if not action_type:
                continue

            channel = "notification"
            target = act.get("target")

            payload = {
                "kind": kind,
                "request_id": request_id,
                "action": act,
            }

            outbox_id = _stable_outbox_id(str(event_id), channel, action_type, str(target) if target is not None else None)

            conn.execute(
                """
                INSERT OR IGNORE INTO outbox(
                    outbox_id,
                    event_id,
                    event_type,
                    aggregate_type,
                    aggregate_id,
                    channel,
                    action_type,
                    target,
                    payload_json,
                    status,
                    attempt_count,
                    next_attempt_at_ms,
                    last_error,
                    created_at_ms,
                    updated_at_ms
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outbox_id,
                    str(event_id),
                    kind,
                    None,
                    None,
                    channel,
                    action_type,
                    str(target) if target is not None else None,
                    __import__("json").dumps(payload, separators=(",", ":"), sort_keys=True),
                    "pending",
                    0,
                    0,
                    None,
                    now_ms,
                    now_ms,
                ),
            )
