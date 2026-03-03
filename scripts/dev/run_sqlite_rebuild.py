from __future__ import annotations

from core.db.config import db_path
from core.dev_sqlite.migrate import migrate
from core.dev_sqlite.rebuild import rebuild

if __name__ == "__main__":
    migrate(db_path())
    rebuild()
