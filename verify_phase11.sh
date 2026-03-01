#!/usr/bin/env bash
set -euo pipefail
python3 ./scripts/phase12_audit_registries.py
bash ./scripts/phase12_legacy_guard.sh
python3 ./scripts/smoke_all.py

test -f src/core/kind_registry.core.json

OUT="$(printf '%s' '{"kind":"STATE_TRANSITION","idempotency":{"request_id":"phase11-verify-1"},"actor":{"actor_id":"u1","role":"system"},"payload":{"actor":{"actor_id":"u1","role":"system"},"entity":{"entity_type":"booking","entity_id":"b1"},"current":{"current_state":"PENDING","current_version":1},"requested":{"requested_state":"CONFIRMED","reason_code":"SMOKE_TEST","request_id":"phase11-verify-1"},"context":{"priority_stack":[],"invariants":"default","related_facts":{}},"time":{"now_utc":"2026-02-28T08:00:00Z"}}}' | python3 .agent/system/event_router.py)"

printf '%s' "$OUT" | python3 -c 'import json,sys; out=json.load(sys.stdin); assert out.get("ok") is True, out; assert out.get("skill")=="state-transition-guard", out; res=out.get("result") or {}; warn=res.get("warnings") or []; assert isinstance(warn,list), warn; assert warn==[], warn; print("PHASE11_OK")'
