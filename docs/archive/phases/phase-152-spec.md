# Phase 152 — iCal Sync-on-Amendment Push

**Status:** Closed
**Prerequisite:** Phase 151 — iCal Cancellation Push
**Date Closed:** 2026-03-10

## Goal

When `BOOKING_AMENDED` is APPLIED, re-push the iCal block to all `ical_fallback`
channels with the **updated check_in / check_out dates**. Best-effort — never blocks.

## Design / Files

| File | Change |
|------|--------|
| `src/services/amend_sync_trigger.py` | NEW — `fire_amend_sync(booking_id, property_id, tenant_id, check_in, check_out, *, channels=None)` |
| `src/adapters/ota/service.py` | MODIFIED — Phase 152 hook after BOOKING_AMENDED APPLIED |
| `tests/test_ical_amend_push_contract.py` | NEW — 35 contract tests, Groups A-J |

### Key design decisions

- **Reuses `ICalPushAdapter.push()`** — not a new method. All Phase 150 timezone support (VTIMEZONE, TZID-qualified dates) and Phase 141–143 resilience (rate-limit, retry, idempotency key) come for free.
- **`_to_ical()`** helper in `amend_sync_trigger.py` normalises both `YYYY-MM-DD` (ISO from `normalize_amendment()`) and `YYYYMMDD` (compact) to `YYYYMMDD`.
- **Timezone forwarded** from the `property_channel_map.timezone` column (Phase 150) — fetched alongside `provider`/`external_id` in `_get_ical_channels()`.
- **`channels` injection param** allows contract tests to bypass DB query, identical to Phase 151 pattern.
- **Position in service.py**: after Phase 115 task-reschedule block (lines 217–231), which already calls `normalize_amendment()`. The Phase 152 block calls `normalize_amendment()` again independently to avoid coupling to Phase 115's local variable scope.

## Result

**3963 tests pass, 2 pre-existing SQLite skips (unchanged).**
No DB schema changes. No API surface changes.
35 new contract tests across Groups A-J.
