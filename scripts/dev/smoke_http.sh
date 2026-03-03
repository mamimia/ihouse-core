#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env" ]]; then
  export IHOUSE_API_KEY="$(grep -E '^IHOUSE_API_KEY=' .env | tail -n 1 | cut -d= -f2-)"
fi

export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

if [[ -z "${IHOUSE_API_KEY:-}" ]]; then
  echo "IHOUSE_API_KEY is not set. Put it in .env (IHOUSE_API_KEY=...) or export it."
  exit 1
fi

PY="$PWD/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing venv python at $PY. Create venv first."
  exit 1
fi

BASE_URL="$BASE_URL" IHOUSE_API_KEY="$IHOUSE_API_KEY" PYTHONPATH=src "$PY" -m pytest -q tests/test_http_smoke.py
