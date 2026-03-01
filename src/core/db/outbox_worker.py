from __future__ import annotations

import os
import sqlite3
import time
import uuid

from typing import List, Optional, Tuple

from core.db.config import db_path
from core.db.sqlite import Sqlite


def _now_ms() -> int:
    return int(time.time() * 1000)


def _backoff_ms(attempt: int) -> int:
    if attempt <= 1:
        return 5_000
    if attempt == 2:
        return 15_000
    if attempt == 3:
        return 60_000
    if attempt == 4:
        return 300_000
    if attempt == 5:
        return 1_800_000
    return 7_200_000


def _max_attempts() -> int:
    try:
        return int(os.getenv("IHOUSE_OUTBOX_MAX_ATTEMPTS", "8"))
    except Exception:
        return 8


def _lease_ms() -> int:
    try:
        return int(os.getenv("IHOUSE_OUTBOX_LEASE_MS", "30000"))
    except Exception:
        return 30_000


def _should_smoke_fail(action_type: str, target: Optional[str]) -> bool:
    rule = (os.getenv("IHOUSE_OUTBOX_SMOKE_FAIL", "") or "").strip()
    if not rule:
        return False
    try:
        want_action, want_target = rule.split(":", 1)
        return action_type == want_action and (target or "") == want_target
    except Exception:
        return False


def _claim_due(
    conn: sqlite3.Connection,
    worker_id: str,
    now_ms: int,
    limit: int,
    lease_ms: int,
) -> List[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT outbox_id
        FROM outbox
        WHERE status IN ('pending','failed')
          AND next_attempt_at_ms <= ?
          AND claimed_until_ms <= ?
        ORDER BY created_at_ms ASC
        LIMIT ?
        """,
        (now_ms, now_ms, limit),
    ).fetchall()

    claimed_ids: List[str] = []

    for r in rows:
        outbox_id = str(r["outbox_id"])
        cur = conn.execute(
            """
            UPDATE outbox
            SET claimed_by = ?, claimed_until_ms = ?, updated_at_ms = ?
            WHERE outbox_id = ?
              AND status IN ('pending','failed')
              AND next_attempt_at_ms <= ?
              AND claimed_until_ms <= ?
            """,
            (worker_id, now_ms + lease_ms, now_ms, outbox_id, now_ms, now_ms),
        )
        if cur.rowcount == 1:
            claimed_ids.append(outbox_id)

    if not claimed_ids:
        return []

    qmarks = ",".join(["?"] * len(claimed_ids))
    return conn.execute(
        f"""
        SELECT outbox_id, attempt_count, action_type, target
        FROM outbox
        WHERE outbox_id IN ({qmarks})
          AND claimed_by = ?
        """,
        (*claimed_ids, worker_id),
    ).fetchall()


def process_once(
    dbfile: Optional[str] = None,
    limit: int = 50,
    now_ms: Optional[int] = None,
) -> Tuple[int, int]:
    ts = int(now_ms) if now_ms is not None else _now_ms()
    path = dbfile or db_path()
    max_attempts = _max_attempts()
    lease_ms = _lease_ms()
    worker_id = os.getenv("IHOUSE_WORKER_ID", "") or f"w_{uuid.uuid4().hex}"

    db = Sqlite(path)
    conn = db.connect()
    try:
        conn.row_factory = sqlite3.Row
        sent = 0
        failed = 0

        with conn:
            claimed = _claim_due(conn, worker_id, ts, limit, lease_ms)

            for r in claimed:

                outbox_id = str(r["outbox_id"])
                attempt_count = int(r["attempt_count"] or 0)
                action_type = str(r["action_type"] or "")
                target = r["target"]
                target_s = str(target) if target is not None else None

                next_attempt = attempt_count + 1

                if _should_smoke_fail(action_type, target_s):
                    failed += 1
                    if next_attempt >= max_attempts:
                        conn.execute(
                            """
                            UPDATE outbox
                            SET status='failed',
                                attempt_count=?,
                                next_attempt_at_ms=?,
                                last_error=?,
                                claimed_by=NULL,
                                claimed_until_ms=0,
                                updated_at_ms=?
                            WHERE outbox_id=?
                              AND claimed_by=?
                            """,
                            (next_attempt, 2_147_483_647_000, "SMOKE_FAIL: max_attempts reached", ts, outbox_id, worker_id),
                        )
                    else:
                        delay = _backoff_ms(next_attempt)
                        conn.execute(
                            """
                            UPDATE outbox
                            SET status='failed',
                                attempt_count=?,
                                next_attempt_at_ms=?,
                                last_error=?,
                                claimed_by=NULL,
                                claimed_until_ms=0,
                                updated_at_ms=?
                            WHERE outbox_id=?
                              AND claimed_by=?
                            """,
                            (next_attempt, ts + delay, "SMOKE_FAIL: simulated delivery failure", ts, outbox_id, worker_id),
                        )
                    continue

                sent += 1
                conn.execute(
                    """
                    UPDATE outbox
                    SET status='sent',
                        attempt_count=?,
                        next_attempt_at_ms=0,
                        last_error=NULL,
                        claimed_by=NULL,
                        claimed_until_ms=0,
                        updated_at_ms=?
                    WHERE outbox_id=?
                      AND claimed_by=?
                    """,
                    (next_attempt, ts, outbox_id, worker_id),
                )

        return sent, failed
    finally:
        conn.close()


if __name__ == "__main__":
    s, f = process_once()
    print(f"OUTBOX WORKER OK. sent={s} failed={f}")
