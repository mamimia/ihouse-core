# Phase 349 — Outbound Sync Coverage Expansion

**Closed:** 2026-03-12
**Category:** 📤 Outbound Sync / Testing
**Test file:** `tests/test_outbound_coverage_p349.py`

## Summary

First-ever dedicated tests for `booking_dates.py` (iCal date lookup) and
`bookingcom_content.py` (Content API payload builder + push). Also covers
outbound adapter registry, iCal push adapter, and base-class helpers
(idempotency key, throttle, retry).

## Tests Added: 31

### Group A — Booking Dates (6 tests)
- iCal format, missing booking, DB error, null dates, tenant isolation

### Group B — Content Payload Builder (8 tests)
- Valid payload, optional fields, missing hotel_id/name/address, country code, description truncation

### Group C — Content Push E2E (6 tests)
- Dry-run, fields_pushed, validation error, HTTP 200, HTTP 400, network error

### Group D — Registry + iCal Push (6 tests)
- 7 providers registered, unknown returns None, iCal dry-run, Expedia/VRBO shared adapter

### Group E — Base Helpers (5 tests)
- Idempotency key format/suffix/stability, throttle disabled, AdapterResult shape

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 6,939 | 6,970 |
| Test files | 232 | 233 |
| New tests | — | 31 |
