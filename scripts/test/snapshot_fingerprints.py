import sys
from pathlib import Path
from contextlib import redirect_stdout
import io
import json

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from core.db.rebuild import rebuild
from core.db.validate_rebuild import snapshot_fingerprints

def main() -> None:
    # Silence rebuild prints to keep JSON output clean
    buf = io.StringIO()
    with redirect_stdout(buf):
        rebuild()
    fps = snapshot_fingerprints()
    print(json.dumps(fps))

if __name__ == "__main__":
    main()
