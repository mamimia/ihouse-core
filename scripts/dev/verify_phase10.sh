#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.." || exit 1

source .venv/bin/activate

echo "1) Unit tests"
python -m pytest -q

echo "2) Smoke events"
for f in smoke_events/*.json; do
  cat "$f" | python3 .agent/system/event_router.py >/dev/null
done

echo "3) Negative"
echo "not json" | python3 .agent/system/event_router.py | python3 -m json.tool >/dev/null
echo "\"hello\"" | python3 .agent/system/event_router.py | python3 -m json.tool >/dev/null

echo "OK"
