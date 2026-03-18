#!/usr/bin/env bash
# iHouse Core — Backend Production/Simple Start
# ==============================================
# See docs/ops/runtime-truth.md for full context.
# Entrypoint: src/main.py (NOT src/app/main.py)
# Port: 8000 canonical dev / uses PORT env if set
set -euo pipefail

cd "$(dirname "$0")/.."

source .venv/bin/activate

set -a
source .env
set +a

export PYTHONPATH=src
export PORT="${PORT:-8000}"
export HOST="${HOST:-127.0.0.1}"

echo "[ihouse] Starting backend on ${HOST}:${PORT}"

exec python -m uvicorn main:app --host "${HOST}" --port "${PORT}"
