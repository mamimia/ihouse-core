from __future__ import annotations

import hashlib
import sqlite3
from typing import List, Dict, Any, Tuple

from core.db.config import db_path
from core.db.rebuild import rebuild

MATERIALIZED_TABLES = [
    "bookings",
    "conflict_tasks",
    "booking_overrides",
    "notifications",
]


def _table_fingerprint(conn: sqlite3.Connection, table: str) -> Dict[str, Any]:
    # Deterministic order: by all columns (pragma order), ascending.
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if not cols:
        return {"table": table, "rows": 0, "sha256": ""}

    order_by = ", ".join([f'"{c}" ASC' for c in cols])
    select_cols = ", ".join([f'"{c}"' for c in cols])

    rows = conn.execute(f'SELECT {select_cols} FROM {table} ORDER BY {order_by}').fetchall()

    h = hashlib.sha256()
    for r in rows:
        # Canonical encoding: join with unit separator, represent None as empty.
        parts = []
        for c in cols:
            v = r[c]
            parts.append("" if v is None else str(v))
        line = "\x1f".join(parts) + "\n"
        h.update(line.encode("utf-8"))

    return {"table": table, "rows": len(rows), "sha256": h.hexdigest()}


def snapshot_fingerprints() -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path())
    try:
        conn.row_factory = sqlite3.Row
        return [_table_fingerprint(conn, t) for t in MATERIALIZED_TABLES]
    finally:
        conn.close()


def validate() -> int:
    # Rebuild #1
    rebuild()
    fp1 = snapshot_fingerprints()

    # Rebuild #2
    rebuild()
    fp2 = snapshot_fingerprints()

    ok = fp1 == fp2

    out = {
        "ok": ok,
        "tables": MATERIALIZED_TABLES,
        "fingerprints_1": fp1,
        "fingerprints_2": fp2,
    }
    print(out)

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(validate())
