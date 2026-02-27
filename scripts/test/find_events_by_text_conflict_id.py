import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import sqlite3
from core.db.config import db_path
from core.db.sqlite import Sqlite
NEEDLE = "conflict_b_new_001_smoke_booking_conflict_001"

def main() -> None:
    conn = Sqlite(path=db_path()).connect()
    try:
        rows = conn.execute(
            """
            SELECT row_id, event_id, ts_ms, kind, request_json, response_json
            FROM events
            WHERE request_json LIKE ? OR response_json LIKE ?
            ORDER BY row_id ASC
            """,
            (f"%{NEEDLE}%", f"%{NEEDLE}%")
        ).fetchall()

        print(f"found={len(rows)}")
        for r in rows:
            print("-----")
            print("row_id:", r["row_id"])
            print("event_id:", r["event_id"])
            print("ts_ms:", r["ts_ms"])
            print("kind:", r["kind"])
            print("request_json_snip:", r["request_json"][:800].replace("\n", " "))
            print("response_json_snip:", r["response_json"][:800].replace("\n", " "))
    finally:
        conn.close()

if __name__ == "__main__":
    main()
