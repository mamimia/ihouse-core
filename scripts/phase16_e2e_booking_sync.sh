#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -f ".env" ]; then
  set -a
  source ./.env
  set +a
fi

export PYTHONPATH="${PYTHONPATH:-}:src"

KEY="${IHOUSE_API_KEY:-}"
if [ -z "$KEY" ]; then
  echo "IHOUSE_API_KEY missing after loading .env"
  exit 1
fi

DB="${IHOUSE_DB_PATH:-.data/ihouse.sqlite3}"
mkdir -p "$(dirname "$DB")" artifacts

echo "Using DB: $DB"
echo

echo "POST /events"
curl -sS -X POST "http://127.0.0.1:8000/events" \
  -H "Content-Type: application/json" \
  -H "IHOUSE-API-KEY: ${KEY}" \
  -d @- | tee artifacts/phase16_post_events_response.json <<'JSON'
{
  "type": "booking_sync_ingest",
  "occurred_at": "2026-03-01T10:00:00Z",
  "actor": { "actor_id": "test", "role": "system" },
  "idempotency": { "request_id": "phase16-test-0001" },
  "payload": {
    "provider": "airbnb",
    "external_booking_id": "abc123",
    "property_id": "p_001",
    "provider_payload": {
      "status": "confirmed",
      "start_date": "2026-04-01",
      "end_date": "2026-04-05",
      "guest_name": "Alice"
    }
  }
}
JSON

echo
echo "DB check"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB" "select booking_id, version, last_envelope_id from booking_state order by updated_at_ms desc limit 3;"
else
  python3 - <<'PY'
import os, sqlite3
db = os.environ.get("IHOUSE_DB_PATH", ".data/ihouse.sqlite3")
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("select booking_id, version, last_envelope_id from booking_state order by updated_at_ms desc limit 3;")
print(cur.fetchall())
con.close()
PY
fi
