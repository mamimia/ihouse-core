# Phase 151 — iCal Cancellation Push

**Status:** Closed
**Prerequisite:** Phase 150 — iCal VTIMEZONE Support
**Date Closed:** 2026-03-10

## Goal

When `BOOKING_CANCELED` is APPLIED via `apply_envelope`, push a VCALENDAR cancellation
payload (RFC 5545 `METHOD:CANCEL`, `STATUS:CANCELLED`) to all `ical_fallback` channels
mapped for the property. Best-effort — never blocks the main response.

## RFC 5545 Compliance

| Property | Value | Section |
|----------|-------|---------|
| `METHOD` | `CANCEL` | §3.7.2 |
| `STATUS` | `CANCELLED` | §3.8.1.11 |
| `SEQUENCE` | `1` (one ahead of push SEQUENCE:0) | §3.8.7.4 |
| `UID` | `{booking_id}@ihouse.core` — same as original push | §3.8.4.7 |

## Design / Files

| File | Change |
|------|--------|
| `src/services/cancel_sync_trigger.py` | NEW — `fire_cancel_sync(booking_id, property_id, tenant_id, channels=None)` |
| `src/adapters/outbound/ical_push_adapter.py` | MODIFIED — `cancel()` method |
| `src/adapters/ota/service.py` | MODIFIED — Phase 151 hook |
| `tests/test_ical_cancel_push_contract.py` | NEW — 38 contract tests, Groups A-J |

### Key design decisions

- **`cancel_sync_trigger.fire_cancel_sync()`** follows the exact same pattern as `task_writer.cancel_tasks_for_booking_canceled` — best-effort, swallows all exceptions, returns a result list for observability (not for branching).
- **`ICalPushAdapter.cancel()`** reuses all Phase 141–143 infrastructure: `_throttle()`, `_retry_with_backoff()`, `_build_idempotency_key()`.
- **`channels` injection parameter** on `fire_cancel_sync()` allows contract tests to bypass DB without mocking Supabase.
- **`_ICAL_PROVIDERS`** constant in `cancel_sync_trigger.py` is the authoritative gate — only `{hotelbeds, tripadvisor, despegar}` are permitted iCal targets.
- Non-ical providers and unknown providers return `status='skipped'`, not failures.

## Result

**3928 tests pass, 2 pre-existing SQLite skips (unchanged).**
No DB schema changes. No API surface changes.
38 new contract tests across Groups A-J.
