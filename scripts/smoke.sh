#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "missing command: $1"; exit 2; }; }
need curl
need python3

health="$(curl -s "$BASE_URL/health" || true)"
if [ -z "$health" ]; then
  echo "health check failed, is http_adapter running?"
  exit 2
fi

echo "health:"
echo "$health" | python3 -m json.tool
echo

is_ok_true() {
  python3 -c 'import sys,json
d=json.load(sys.stdin)
sys.exit(0 if d.get("ok") is True else 1)
'
}

run_one() {
  file="$1"
  echo "running: $file"

  resp="$(curl -s "$BASE_URL/event" -H "Content-Type: application/json" --data-binary "@$file" || true)"
  if [ -z "$resp" ]; then
    echo "empty response"
    echo "result: FAIL"
    echo
    return 1
  fi

  echo "$resp" | python3 -m json.tool || true

  if echo "$resp" | is_ok_true; then
    echo "result: PASS"
    echo
    return 0
  fi

  echo "result: FAIL"
  echo
  return 1
}

fail=0
run_one "smoke_events/01_state_transition.json" || fail=1
run_one "smoke_events/02_booking_conflict.json" || fail=1
run_one "smoke_events/03_task_completion.json" || fail=1
run_one "smoke_events/04_sla_escalation.json" || fail=1

if [ "$fail" -ne 0 ]; then
  echo "smoke: FAILED"
  exit 1
fi

echo "smoke: OK"
