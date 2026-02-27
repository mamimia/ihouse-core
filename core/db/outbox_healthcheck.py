from __future__ import annotations

import os
import sqlite3
import time

from core.db.config import db_path
from core.db.sqlite import Sqlite


def _now_ms() -> int:
    return int(time.time() * 1000)


def main() -> int:
    threshold_ms = int(os.getenv("IHOUSE_OUTBOX_STUCK_MS", str(10 * 60 * 1000)))  # 10 min default
    ts = _now_ms()

    db = Sqlite(db_path())
    conn = db.connect()
    try:
        # due and not sent
        rows = conn.execute(
            """
            SELECT outbox_id, status, attempt_count, next_attempt_at_ms, updated_at_ms, last_error
            FROM outbox
            WHERE status IN ('pending','failed')
              AND next_attempt_at_ms <= ?
            ORDER BY next_attempt_at_ms ASC
            """,
            (ts,),
        ).fetchall()

        stuck = []
        for r in rows:
            updated = int(r["updated_at_ms"] or 0)
            if ts - updated >= threshold_ms:
                stuck.append((r["outbox_id"], r["status"], r["attempt_count"], r["last_error"]))

        if stuck:
            print("OUTBOX HEALTHCHECK FAIL. stuck_due=", stuck)
            return 1

        print("OUTBOX HEALTHCHECK OK.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
