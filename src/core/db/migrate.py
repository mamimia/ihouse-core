from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from core.db.sqlite import Sqlite, applied_versions, apply_migration

def _load_migrations() -> List[Tuple[int, str]]:
    migrations_dir = Path(__file__).parent / "migrations"
    items: List[Tuple[int, str]] = []
    for p in sorted(migrations_dir.glob("*.sql")):
        v = int(p.name.split("_", 1)[0])
        items.append((v, p.read_text(encoding="utf-8")))
    return items

def migrate(db_path: str) -> None:
    db = Sqlite(db_path)
    conn = db.connect()
    try:
        have = applied_versions(conn)
        for version, sql in _load_migrations():
            if version in have:
                continue
            apply_migration(conn, version, sql)
    finally:
        conn.close()
