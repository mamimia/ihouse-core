import os
from pathlib import Path

def db_path() -> str:
    p = os.getenv("IHOUSE_DB_PATH", ".data/ihouse.sqlite3")
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    return p
