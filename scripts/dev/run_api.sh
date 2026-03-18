#!/usr/bin/env bash
# iHouse Core — Backend Dev Start
# ================================
# Canonical startup script. See docs/ops/runtime-truth.md for full context.
# Entrypoint: src/main.py (NOT src/app/main.py)
# Port: 8000 (canonical dev port)
set -euo pipefail

cd "$(dirname "$0")/../.."

source .venv/bin/activate

set -a
source .env
set +a

export PYTHONPATH="src"
export PORT="${PORT:-8000}"
export HOST="${HOST:-127.0.0.1}"

echo "[ihouse] Starting backend on ${HOST}:${PORT} — entrypoint: src/main.py"

exec python3 -m uvicorn main:app --reload --host "${HOST}" --port "${PORT}" --log-level info
