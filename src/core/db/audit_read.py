from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any, Dict, Optional

from core.db.config import db_path
from core.db.sqlite import Sqlite
def _connect() -> sqlite3.Connection:
    return Sqlite(path=db_path()).connect()


def _parse_json(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return s


def query_events(
    kind: Optional[str],
    request_id: Optional[str],
    actor_id: Optional[str],
    since_ms: Optional[int],
    until_ms: Optional[int],
    limit: int,
) -> list[Dict[str, Any]]:
    sql = "SELECT row_id, event_id, ts_ms, kind, request_json, response_json, runner_stdout, runner_stderr FROM events WHERE 1=1"
    params: list[Any] = []

    if kind:
        sql += " AND kind = ?"
        params.append(kind)

    if since_ms is not None:
        sql += " AND ts_ms >= ?"
        params.append(int(since_ms))

    if until_ms is not None:
        sql += " AND ts_ms <= ?"
        params.append(int(until_ms))

    sql += " ORDER BY row_id DESC LIMIT ?"
    params.append(int(limit))

    out: list[Dict[str, Any]] = []
    conn = _connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            req = _parse_json(r["request_json"])
            resp = _parse_json(r["response_json"])

            # Optional in-memory filters based on envelope fields
            if request_id:
                rid = None
                if isinstance(req, dict):
                    rid = (req.get("idempotency") or {}).get("request_id")
                if rid != request_id:
                    continue

            if actor_id:
                aid = None
                if isinstance(req, dict):
                    aid = (req.get("actor") or {}).get("actor_id")
                if aid != actor_id:
                    continue

            out.append(
                {
                    "row_id": r["row_id"],
                    "event_id": r["event_id"],
                    "ts_ms": r["ts_ms"],
                    "kind": r["kind"],
                    "request": req,
                    "response": resp,
                    "runner_stdout": r["runner_stdout"],
                    "runner_stderr": r["runner_stderr"],
                }
            )
    finally:
        conn.close()

    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Read iHouse audit events from SQLite.")
    p.add_argument("--kind", default=None)
    p.add_argument("--request-id", default=None)
    p.add_argument("--actor-id", default=None)
    p.add_argument("--since-ms", type=int, default=None)
    p.add_argument("--until-ms", type=int, default=None)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--pretty", action="store_true")
    args = p.parse_args()

    events = query_events(
        kind=args.kind,
        request_id=args.request_id,
        actor_id=args.actor_id,
        since_ms=args.since_ms,
        until_ms=args.until_ms,
        limit=args.limit,
    )

    if args.pretty:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(events, ensure_ascii=False))


if __name__ == "__main__":
    main()
