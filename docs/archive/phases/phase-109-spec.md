# Phase 109 — Booking Date Range Search

**Status:** Closed
**Prerequisite:** Phase 108 (Financial List Query API)
**Date Closed:** 2026-03-09

## Goal

Extend `GET /bookings` (Phase 106) with date range filtering: `?check_in_from=YYYY-MM-DD` and `?check_in_to=YYYY-MM-DD`. Each is optional and independent. Add ISO 8601 date validation — 400 VALIDATION_ERROR on bad format.

## Invariant (locked Phase 62+)

These endpoints must NEVER write to `booking_state` or `event_log`. Strictly read-only projection endpoints.

## Design / Files

| File | Change |
|------|--------|
| `src/api/bookings_router.py` | MODIFIED — Phase 109 added to docstring; `import re as _re`; `_DATE_RE` constant; `check_in_from` + `check_in_to` params added to `list_bookings`; date validation before DB call; `gte`/`lte` query filters |
| `tests/test_booking_date_range_contract.py` | NEW — 36 tests, Groups A–F |

## Endpoint Contract

```
GET /bookings
  ?check_in_from=YYYY-MM-DD  (optional — gte filter on check_in column)
  ?check_in_to=YYYY-MM-DD    (optional — lte filter on check_in column)
  -- all existing Phase 106 params preserved --

400 VALIDATION_ERROR if:
  - check_in_from present but not matching ^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])$
  - check_in_to present but not matching same regex

detail field contains the name of the invalid param (check_in_from or check_in_to).
```

## Test Groups

| Group | What it tests |
|-------|---------------|
| A | 200 success: from-only, to-only, both, combined with status, empty result |
| B | 400 validation: 9 bad check_in_from formats, 5 bad check_in_to formats, valid dates accepted |
| C | Compound: date + property_id, all four filters, date + limit |
| D | Edge cases: same from/to, no date params still works, end-of-month dates, no event_log touch |
| E | 400 contract: code + detail body fields present for both params |
| F | Regression: property_id, status, invalid status, limit clamping all still work |

## Result

**2437 tests pass, 2 pre-existing SQLite skips.**
No schema changes. No migrations. `booking_state` read-only.
