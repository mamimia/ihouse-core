from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Sqlite:
    path: str

    def connect(self) -> sqlite3.Connection:
        # timeout=30 here is sqlite3's built-in busy handler (seconds)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row

        # Phase 7 hardening: enforce per-connection PRAGMAs (do not rely on manual CLI)
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA wal_autocheckpoint=1000;")

        return conn


def _now_ms() -> int:
    return int(time.time() * 1000)


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          applied_at_ms INTEGER NOT NULL
        )
        """
    )


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    ensure_schema(conn)
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return {int(r["version"]) for r in rows}


def apply_migration(conn: sqlite3.Connection, version: int, sql: str) -> None:
    ensure_schema(conn)
    with conn:
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at_ms) VALUES(?, ?)",
            (version, _now_ms()),
        )


def append_event(
    conn: sqlite3.Connection,
    kind: str,
    request_envelope: Dict[str, Any],
    response_payload: Dict[str, Any],
    runner_stdout: Optional[str] = None,
    runner_stderr: Optional[str] = None,
    ts_ms: Optional[int] = None,
) -> str:
    """
    Append-only write into events with idempotency.

    Rule:
    - event_id is request_id if present
    - if missing, use anon_<ts_ms> to avoid collisions
    - DB enforces uniqueness on event_id
    - duplicates are ignored (idempotent no-op)
    """
    ts = int(ts_ms) if ts_ms is not None else _now_ms()

    raw_event_id = request_envelope.get("idempotency", {}).get("request_id", "")
    event_id = str(raw_event_id) if raw_event_id else f"anon_{ts}"

    k = kind if isinstance(kind, str) else ""

    with conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO events(
                event_id,
                ts_ms,
                kind,
                request_json,
                response_json,
                runner_stdout,
                runner_stderr
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                ts,
                k,
                json.dumps(request_envelope, separators=(",", ":"), ensure_ascii=False),
                json.dumps(response_payload, separators=(",", ":"), ensure_ascii=False),
                runner_stdout,
                runner_stderr,
            ),
        )

    return event_id
