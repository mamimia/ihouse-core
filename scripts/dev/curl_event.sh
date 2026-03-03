#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

if [[ -f ".env" ]]; then
  export IHOUSE_API_KEY="$(grep -E '^IHOUSE_API_KEY=' .env | tail -n 1 | cut -d= -f2-)"
fi

if [[ -z "${IHOUSE_API_KEY:-}" ]]; then
  echo "IHOUSE_API_KEY is not set. Put it in .env (IHOUSE_API_KEY=...) or export it."
  exit 1
fi

EVENT_TYPE="${1:-BOOKING_CREATED}"
REQ_ID="${2:-curl-001}"
BOOKING_ID="${3:-demo-1}"

curl -sS -X POST "$BASE_URL/events" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $IHOUSE_API_KEY" \
  -d "{
    \"type\": \"$EVENT_TYPE\",
    \"idempotency\": {\"request_id\": \"$REQ_ID\"},
    \"actor\": {\"actor_id\": \"system\", \"role\": \"system\"},
    \"payload\": {\"booking_id\": \"$BOOKING_ID\"}
  }"
echo
