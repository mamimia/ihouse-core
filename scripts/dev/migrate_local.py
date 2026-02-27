import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from core.db.config import db_path
from core.db.migrate import migrate

if __name__ == "__main__":
    migrate(db_path())
    print("MIGRATE OK:", db_path())
