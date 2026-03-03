from __future__ import annotations

import argparse
import sqlite3
from typing import Dict, Any, List, Tuple

def replay(db_file: str, limit: int) -> Dict[str, Any]:
    from core.db.sqlite import Sqlite
    conn = Sqlite(path=db_file).connect()
    try:
        last = conn.execute("SELECT COALESCE(MAX(row_id), 0) AS m FROM events").fetchone()["m"]
        rows = conn.execute(
            "SELECT kind, COUNT(*) AS n FROM (SELECT kind FROM events ORDER BY row_id DESC LIMIT ?) GROUP BY kind ORDER BY kind",
            (limit,),
        ).fetchall()
        by_kind = {r["kind"]: int(r["n"]) for r in rows}
        return {"ok": True, "db": db_file, "limit": limit, "last_row_id": int(last), "counts_by_kind": by_kind}
    finally:
        conn.close()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=".data/ihouse.sqlite3")
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()
    out = replay(args.db, args.limit)
    print(out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
