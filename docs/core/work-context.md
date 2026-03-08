# iHouse Core — Work Context

## Current Active Phase

Phase 58 — HTTP Ingestion Layer (closed)

## Last Closed Phase

Phase 57 — Webhook Signature Verification

## Current Objective

Phase 58 is closed. Phase 59 is TBD.

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical
- HTTP endpoint does not call `apply_envelope` directly — routes through `ingest_provider_event` → pipeline → `IngestAPI.append_event` → `CoreExecutor.execute` → `apply_envelope`

## Key Files Added in Phase 58

| File | Role |
|------|------|
| `src/api/__init__.py` | Package init |
| `src/api/webhooks.py` | FastAPI router — `POST /webhooks/{provider}` |
| `tests/test_webhook_endpoint.py` | 16 contract tests (TestClient, CI-safe) |

## HTTP Status Codes (locked)

| Code | Meaning |
|------|---------|
| 200 | ACCEPTED — envelope created |
| 400 | PAYLOAD_VALIDATION_FAILED |
| 403 | SIGNATURE_VERIFICATION_FAILED |
| 500 | INTERNAL_ERROR |

## Supabase

- Project: `reykggmlcehswrxjviup`
- URL: `https://reykggmlcehswrxjviup.supabase.co`
- No new migrations in Phase 58

## Tests

286 passing (2 pre-existing SQLite skips, unrelated)
