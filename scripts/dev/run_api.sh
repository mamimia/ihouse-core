#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

source .venv/bin/activate

set -a
source .env
set +a

export PYTHONPATH="src"
export DB_ADAPTER="${DB_ADAPTER:-supabase}"
export PORT="${PORT:-8000}"
export HOST="${HOST:-127.0.0.1}"

# Phase 14 stabilization: routed/agent sidecars must not write event_log/state implicitly
export AGENT_SIDECAR_APPLY="0"

exec python3 -m uvicorn app.main:app --reload --host "$HOST" --port "$PORT" --log-level info
