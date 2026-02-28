#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

python -m pip install --upgrade pip >/dev/null
pip install pytest >/dev/null

export PYTHONPATH="$REPO_ROOT"
export DB_PATH="${DB_PATH:-./.data/ihouse.sqlite3}"

python -m core.db.validate_rebuild >/tmp/validate_rebuild.txt
pytest -q
sqlite3 "$DB_PATH" <<'SQL'
PRAGMA quick_check;
PRAGMA foreign_key_check;
SQL

echo "PHASE7_VERIFY_OK"
