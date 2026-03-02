from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Dict, List, Literal


Kind = str


def _eid() -> str:
    return str(uuid.uuid4())


def _coerce_emitted(third_arg: Any) -> List[Dict[str, Any]]:
    if isinstance(third_arg, list):
        return [x for x in third_arg if isinstance(x, dict)]
    if isinstance(third_arg, dict):
        v = third_arg.get("emitted_events", [])
        if isinstance(v, list):
            return [x for x in v if isinstance(x, dict)]
    return []


def apply_result(
    conn: sqlite3.Connection,
    envelope: Dict[str, Any],
    third_arg: Any,
) -> Literal["APPLIED", "ALREADY_APPLIED"]:
    """
    Minimal SQLite event log applier.

    Accepts either:
      third_arg = emitted_events: List[Dict[str, Any]]
    or
      third_arg = {"emitted_events": List[Dict[str, Any]]}

    Envelope required keys:
      envelope_id: str
      occurred_at: str
    """

    envelope_id = envelope["envelope_id"]
    occurred_at = envelope["occurred_at"]
    emitted = _coerce_emitted(third_arg)

    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE")

        cur.execute(
            """
            INSERT OR IGNORE INTO event_log(event_id, envelope_id, kind, occurred_at, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                envelope_id,
                envelope_id,
                "envelope_received",
                occurred_at,
                json.dumps(envelope, separators=(",", ":")),
            ),
        )

        cur.execute("SELECT changes()")
        if cur.fetchone()[0] == 0:
            cur.execute("ROLLBACK")
            return "ALREADY_APPLIED"

        for ev in emitted:
            kind_val = ev.get("kind") or ev.get("type")
            if not isinstance(kind_val, str) or not kind_val:
                raise ValueError("EMITTED_EVENT_KIND_REQUIRED")
            payload = ev.get("payload", ev)

            cur.execute(
                """
                INSERT INTO event_log(event_id, envelope_id, kind, occurred_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _eid(),
                    envelope_id,
                    kind_val,
                    occurred_at,
                    json.dumps(payload, separators=(",", ":")),
                ),
            )

        cur.execute("COMMIT")
        return "APPLIED"
    except Exception:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        raise
