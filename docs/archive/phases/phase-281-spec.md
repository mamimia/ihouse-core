# Phase 281 — First Live OTA Integration Test

**Status:** Closed
**Prerequisite:** Phase 280 (Real Webhook Endpoint Validation)
**Date Closed:** 2026-03-11

## Goal

Build a production-ready live staging harness for end-to-end OTA integration testing — from raw HTTP webhook → HMAC verification → payload normalization → apply_envelope RPC → Supabase event_log — without any mocking between layers.

## Files Created

### `scripts/e2e_live_ota_staging.py` — Live Staging Runner

4-step live integration test:

| Step | Action | What's tested |
|------|--------|---------------|
| 1 | Build canonical Booking.com payload | Payload format matches production |
| 2 | Compute HMAC-SHA256 signature | Signing matches `X-Booking-Signature` header |
| 3 | POST to `/webhooks/bookingcom` | Full API stack: JWT → HMAC → ingest |
| 4 | Query Supabase `event_log` | Verify row written (real DB check) |

Usage:
```bash
# Dry-run (no live services needed)
python3 scripts/e2e_live_ota_staging.py --dry-run

# Live test (API running on port 8000, Supabase secrets set)
IHOUSE_WEBHOOK_SECRET_BOOKINGCOM=... SUPABASE_URL=... SUPABASE_KEY=... \
IHOUSE_DEV_MODE=true \
python3 scripts/e2e_live_ota_staging.py --base-url http://localhost:8000
```

### `tests/test_live_ota_staging_p281.py` — CI-Safe Companion Tests (15 tests)

| Group | Tests | Coverage |
|-------|-------|----------|
| A — Happy Path | 3 | 200, idempotency_key, provider= bookingcom |
| B — HMAC Gate | 3 | Wrong secret, body tampering, missing header |
| C — Payload Validation | 3 | Missing fields, empty, non-JSON |
| D — Dry-Run Script | 3 | Exit 0, output check, no network calls |
| E — Idempotency Key | 3 | String, non-empty, deterministic |

## Test Results

```
15/15 passed (CI-safe, no live API or Supabase needed)
Dry-run script verified: exit 0
Full suite: exit 0
```

## Next Step for Real Live Test

To run the actual live integration test against staging:
1. Start API: `./scripts/run_api.sh`
2. Set secrets: `IHOUSE_WEBHOOK_SECRET_BOOKINGCOM`, `SUPABASE_URL`, `SUPABASE_KEY`
3. Run: `python3 scripts/e2e_live_ota_staging.py --base-url http://localhost:8000`

The script verifies the event_log row in Supabase and exits 0 on full pass.
