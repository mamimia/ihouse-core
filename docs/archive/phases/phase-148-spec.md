# Phase 148 — Sync Result Webhook Callback

**Status:** Closed  
**Prerequisite:** Phase 147 (Failed Sync Replay)  
**Date Closed:** 2026-03-10

## Goal

Add a best-effort HTTP POST callback after every successful outbound sync result.
When `IHOUSE_SYNC_CALLBACK_URL` is configured, the executor fires a JSON payload to that URL
after a sync result of status `ok`. The callback is non-blocking, never retried, and swallows
all errors to ensure it never affects the primary sync path.

## Invariant

Callback failures are always silently swallowed. The outbound sync result is persisted before
the callback fires. A missing or unconfigured `IHOUSE_SYNC_CALLBACK_URL` is a noop.

## Design / Files

| File | Change |
|------|--------|
| `src/services/outbound_executor.py` | MODIFIED — added `_CALLBACK_URL` (reads env), `_fire_callback()` helper, called after `_persist()` in `execute_sync_plan()` |
| `tests/test_sync_callback_contract.py` | NEW — 30 contract tests (Groups A–J) |

### Callback payload shape
```json
{
  "event": "sync.ok",
  "booking_id": "...",
  "tenant_id": "...",
  "provider": "...",
  "external_id": "...",
  "strategy": "...",
  "http_status": 200
}
```

## Result

**3799 tests pass, 2 pre-existing SQLite skips (unrelated).**
No DB schema changes. No API route changes.
