# Phase 334 — Booking Dates + iCal Push Adapter Integration Tests

**Status:** Closed
**Prerequisite:** Phase 333 (Booking.com Content Adapter Integration Tests)
**Date Closed:** 2026-03-12

## Goal

First-ever integration tests for:
- `adapters/outbound/booking_dates.py` — Phase 140 (87 lines) injectable Supabase client
- `adapters/outbound/ical_push_adapter.py` — Phase 150 (371 lines) iCal body building

## Files Changed

| File | Change |
|------|--------|
| `tests/test_booking_dates_ical_integration.py` | NEW — 13 tests |

## Test Coverage

| Group | Tests | What |
|-------|-------|------|
| A — fetch_booking_dates | 4 | Valid booking, not found, DB error (fail-safe), compact date |
| B — _build_ical_body UTC | 4 | booking_id, DTSTART/DTEND, VCALENDAR structure, external_id |
| C — _build_ical_body TZ | 3 | VTIMEZONE block, TZID-qualified DTSTART, matching TZID |
| D — iCal Date Format | 2 | ISO→compact, compact unchanged |

## Result

**13 tests. 13 passed. 0 failed. 0.18s. Exit 0.**
