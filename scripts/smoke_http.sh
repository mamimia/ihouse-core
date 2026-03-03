#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

echo "health:"
curl -sS "$BASE_URL/health"
echo
echo

echo "events:"
curl -sS -X POST "$BASE_URL/events" \
  -H "Content-Type: application/json" \
  --data-binary @- <<'JSON'
{
  "REPLACE_ME": "SEE app/main.py /events signature"
}
JSON
echo
echo
