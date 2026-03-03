#!/usr/bin/env bash
set -euo pipefail

source .venv/bin/activate
export PYTHONPATH=src

exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
