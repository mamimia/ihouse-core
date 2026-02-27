import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path for "import core.*"
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Also set PYTHONPATH for any downstream imports that rely on env
os.environ["PYTHONPATH"] = str(REPO_ROOT)
