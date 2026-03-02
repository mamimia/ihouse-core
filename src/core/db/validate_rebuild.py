from __future__ import annotations

import os
import json
import hashlib
import sqlite3
from typing import List, Dict, Any, Mapping

from dotenv import load_dotenv

from core.db.config import db_path
from core.db.rebuild import rebuild
from core.db.sqlite import Sqlite


MATERIALIZED_TABLES = [
    "bookings",
    "conflict_tasks",
    "booking_overrides",
    "notifications",
]


def _stable_json(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return str(v)


def _sha256_lines(lines: List[str]) -> str:
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _table_fingerprint(conn: sqlite3.Connection, table: str) -> Dict[str, Any]:
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if not cols:
        return {"table": table, "rows": 0, "sha256": ""}

    order_by = ", ".join([f'"{c}" ASC' for c in cols])
    select_cols = ", ".join([f'"{c}"' for c in cols])

    rows = conn.execute(f"SELECT {select_cols} FROM {table} ORDER BY {order_by}").fetchall()

    lines: List[str] = []
    for r in rows:
        parts = []
        for c in cols:
            parts.append("" if r[c] is None else str(r[c]))
        lines.append("\x1f".join(parts))

    return {"table": table, "rows": len(rows), "sha256": _sha256_lines(lines)}


def snapshot_fingerprints_sqlite() -> List[Dict[str, Any]]:
    conn = Sqlite(path=db_path()).connect()
    try:
        return [_table_fingerprint(conn, t) for t in MATERIALIZED_TABLES]
    finally:
        conn.close()


def _supabase_client():
    load_dotenv(dotenv_path=".env")

    from supabase import create_client

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    return create_client(supabase_url, supabase_key)


def snapshot_fingerprints_supabase() -> Dict[str, Any]:
    sb = _supabase_client()

    ev = (
        sb.table("event_log")
        .select("event_id,kind,occurred_at")
        .order("occurred_at", desc=False)
        .order("event_id", desc=False)
        .execute()
    )
    ev_rows = ev.data or []
    ev_lines = [
        f'{r.get("occurred_at","")}\x1f{r.get("event_id","")}\x1f{r.get("kind","")}'
        for r in ev_rows
    ]
    event_log_fp = {"rows": len(ev_rows), "sha256": _sha256_lines(ev_lines)}

    st = (
        sb.table("booking_state")
        .select("booking_id,version,last_event_id,state_json")
        .order("booking_id", desc=False)
        .execute()
    )
    st_rows = st.data or []
    st_lines: List[str] = []
    for r in st_rows:
        st_lines.append(
            "\x1f".join(
                [
                    _stable_json(r.get("booking_id")),
                    _stable_json(r.get("version")),
                    _stable_json(r.get("last_event_id")),
                    _stable_json(r.get("state_json")),
                ]
            )
        )
    booking_state_fp = {"rows": len(st_rows), "sha256": _sha256_lines(st_lines)}

    return {"event_log": event_log_fp, "booking_state": booking_state_fp}


def validate() -> int:
    adapter = os.getenv("DB_ADAPTER", "supabase").strip().lower()

    if adapter == "supabase":
        fp1 = snapshot_fingerprints_supabase()
        fp2 = snapshot_fingerprints_supabase()
        ok = fp1 == fp2
        print({"ok": ok, "adapter": "supabase", "fingerprints_1": fp1, "fingerprints_2": fp2})
        return 0 if ok else 2

    rebuild()
    fp1s = snapshot_fingerprints_sqlite()
    rebuild()
    fp2s = snapshot_fingerprints_sqlite()
    ok = fp1s == fp2s
    print(
        {
            "ok": ok,
            "adapter": "sqlite",
            "tables": MATERIALIZED_TABLES,
            "fingerprints_1": fp1s,
            "fingerprints_2": fp2s,
        }
    )
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(validate())
