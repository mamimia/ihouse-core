import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from core.db.rebuild import rebuild

if __name__ == "__main__":
    rebuild()
