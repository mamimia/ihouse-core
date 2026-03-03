import os

def require_sqlite_enabled() -> None:
    allow = os.getenv("IHOUSE_ALLOW_SQLITE", "").lower() in ("1", "true", "yes")
    if not allow:
        raise RuntimeError("SQLite dev tools are disabled. Set IHOUSE_ALLOW_SQLITE=1 to enable.")
