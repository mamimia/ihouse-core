# Phase 129 — Booking Search Enhancement

**Status:** Closed
**Prerequisite:** Phase 128 (Conflict Center)
**Date Closed:** 2026-03-09

## Goal

Enhance `GET /bookings` with a full search/filter surface for operational use.
Operators need to find bookings by OTA provider, checkout range, and control ordering.
This was missing from phases 106/109 which only covered property/status/check_in filtering.

## Changes to `GET /bookings`

### New parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `source` | string (optional) | Filter by OTA provider name (bookingcom, airbnb, etc.) |
| `check_out_from` | date YYYY-MM-DD (optional) | check_out ≥ this date |
| `check_out_to` | date YYYY-MM-DD (optional) | check_out ≤ this date |
| `sort_by` | enum (optional) | `check_in` \| `check_out` \| `updated_at` \| `created_at` (default: `updated_at`) |
| `sort_dir` | enum (optional) | `asc` \| `desc` (default: `desc`) |

### New response fields

```json
{
  "sort_by": "check_in",
  "sort_dir": "asc"
}
```

## Design Decisions

- **No new table.** Pure enhancement to existing `GET /bookings` → `booking_state` query.
- **Backward compatible.** All existing callers unaffected.
- **Validation:** `sort_by` and `sort_dir` validated against whitelists → 400 on invalid.
- **Date validation loop:** single consolidated loop for all 4 date params.
- **Source is no-whitelist:** any string passed to DB (DB rejects unknown providers naturally).
- **Zero write-path changes.**

## Files Changed

| File | Change |
|------|--------|
| `src/api/bookings_router.py` | MODIFIED — Phase 129 filters and sorting |
| `tests/test_booking_search_contract.py` | NEW — 31 tests |

## Result

**3236 tests pass** (2 pre-existing SQLite skips).
