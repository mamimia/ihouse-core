from __future__ import annotations

import json
from typing import Dict, Any, Set

from core.db.config import db_path
from core.db.sqlite import Sqlite
from core.db.projector import project_event


MATERIALIZED_TABLES = [
    "bookings",
    "conflict_tasks",
    "booking_overrides",
    "notifications",
]


def _safe_json(s: str) -> Dict[str, Any]:
    try:
        return json.loads(s) if s else {}
    except Exception:
        return {}


def _required_property_ids_from_responses(conn) -> Set[str]:
    """
    Build required property_ids from the SAME payload the projector uses for bookings writes:
    response_json.result.booking_record.property_id for BOOKING_SYNC_INGEST events where ok=True.
    """
    req: Set[str] = set()
    rows = conn.execute(
        """
        SELECT response_json
        FROM events
        WHERE kind = 'BOOKING_SYNC_INGEST'
        """
    ).fetchall()

    for r in rows:
        resp = _safe_json(r["response_json"])
        if not isinstance(resp, dict) or not resp.get("ok"):
            continue

        result = resp.get("result") or {}
        if not isinstance(result, dict):
            continue

        rec = result.get("booking_record") or {}
        if not isinstance(rec, dict):
            continue

        pid = rec.get("property_id")
        if pid:
            req.add(str(pid))

    return req


def _existing_property_ids(conn) -> Set[str]:
    rows = conn.execute("SELECT property_id FROM properties").fetchall()
    return {str(r["property_id"]) for r in rows}


def rebuild() -> None:
    db = Sqlite(db_path())
    conn = db.connect()

    try:
        # Preflight: properties must cover all property_ids that will be written into bookings
        req = _required_property_ids_from_responses(conn)
        exist = _existing_property_ids(conn)
        missing = sorted([p for p in req if p not in exist])

        if missing:
            raise RuntimeError(
                "REBUILD BLOCKED: missing properties referenced by BOOKING_SYNC_INGEST projections. "
                f"missing_property_ids={missing}"
            )

        with conn:
            # 1. Clear materialized tables only (NEVER delete events or reference tables)
            for table in MATERIALIZED_TABLES:
                conn.execute(f"DELETE FROM {table}")

        # 2. Replay events deterministically
        rows = conn.execute(
            """
            SELECT row_id, kind, request_json, response_json, ts_ms
            FROM events
            ORDER BY row_id ASC
            """
        ).fetchall()

        for r in rows:
            kind = r["kind"]
            envelope = _safe_json(r["request_json"])
            response = _safe_json(r["response_json"])
            ts_ms = int(r["ts_ms"])

            project_event(
                conn=conn,
                kind=kind,
                envelope=envelope,
                response=response,
                now_ms=ts_ms,  # deterministic injection from event timestamp
            )

        print(f"REBUILD OK. Replayed {len(rows)} events.")

    finally:
        conn.close()


if __name__ == "__main__":
    rebuild()
