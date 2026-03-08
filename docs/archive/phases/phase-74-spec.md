# Phase 74 — OTA Date/Timezone Normalization

**Status:** Closed
**Prerequisite:** Phase 73 (Ordering Buffer Auto-Route)
**Date Closed:** 2026-03-09

## Problem Solved

Before this phase, check_in/check_out dates from OTA providers were stored as raw strings — whatever the provider sent. Booking.com sends `"2026-09-01"`, Airbnb sends `"2026-09-01T00:00:00Z"`, Trip.com sends `"20260901"`. No canonical format was enforced anywhere in the Python pipeline.

## Solution

`src/adapters/ota/date_normalizer.py` — a zero-dependency module with `normalize_date(raw)` that normalizes to `"YYYY-MM-DD"` or returns `None`. Integrated into all 5 provider amendment extractors.

## Supported Formats

| Format | Example | Source |
|--------|---------|--------|
| ISO date | `"2026-09-01"` | Booking.com, Expedia |
| ISO datetime UTC | `"2026-09-01T00:00:00Z"` | Airbnb |
| ISO datetime no tz | `"2026-09-01T00:00:00"` | some providers |
| ISO datetime with offset | `"2026-09-01T00:00:00+07:00"` | Agoda |
| Compact YYYYMMDD | `"20260901"` | Trip.com |
| DD/MM/YYYY slash | `"01/09/2026"` | regional |

## Files

| File | Change |
|------|--------|
| `src/adapters/ota/date_normalizer.py` | NEW — `normalize_date()` |
| `src/adapters/ota/amendment_extractor.py` | MODIFIED — all 5 providers now normalize dates |
| `tests/test_date_normalizer_contract.py` | NEW — 22 contract tests |

## Invariants

- `normalize_date` never raises — returns None and logs warning on failure
- Output is always `"YYYY-MM-DD"` with no time component
- None input → None output (safe for optional fields)

## Result

**514 tests pass, 2 skipped.**
No schema changes. No migrations.
