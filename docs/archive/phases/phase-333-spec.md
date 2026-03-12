# Phase 333 — Booking.com Content Adapter Integration Tests

**Status:** Closed
**Prerequisite:** Phase 332 (Bulk Operations Integration Tests)
**Date Closed:** 2026-03-12

## Goal

First-ever integration tests for `adapters/outbound/bookingcom_content.py` — the Phase 250 outbound Booking.com content push adapter.

## Files Changed

| File | Change |
|------|--------|
| `tests/test_bookingcom_content_integration.py` | NEW — 19 tests |

## Test Coverage

| Group | Tests | What |
|-------|-------|------|
| A — Required Field Validation | 6 | Valid, missing hotel_id, name, address, invalid country_code, invalid cancellation |
| B — Payload Shape and Content | 9 | hotel_id as string, country_code uppercase, 2000-char truncation, optionals, timing, default cancellation |
| C — list_pushed_fields | 2 | Sorted keys, optional fields in output |
| D — PushResult Shape | 2 | dry_run flag, failure with error |

## Result

**19 tests. 19 passed. 0 failed. 0.08s. Exit 0.**
