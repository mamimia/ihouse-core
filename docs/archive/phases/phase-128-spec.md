# Phase 128 — Conflict Center

**Status:** Closed
**Prerequisite:** Phase 127 (Integration Health Dashboard)
**Date Closed:** 2026-03-09

## Goal

Dedicated conflict visibility surface for all active booking overlaps across all (or one)
properties for a tenant. Sourced from `future-improvements.md`:

> Conflict Detection and Mapping Coverage (priority: medium)
> Visibility layer for overlaps on same property, missing property mapping,
> incomplete canonical coverage, potential overbooking risk.

Phase 126 added per-request CONFLICT detection inside the availability projection.
Phase 128 adds a tenant-scoped, cross-property conflict overview: no date range required.

## Endpoint

```
GET /conflicts?property_id=<optional>
```

JWT Bearer required.

### Response Shape

```json
{
  "tenant_id": "...",
  "conflicts": [
    {
      "property_id": "prop_1",
      "booking_a": "airbnb_X001",
      "booking_b": "bookingcom_R002",
      "overlap_dates": ["2026-04-05", "2026-04-06", "2026-04-07"],
      "overlap_start": "2026-04-05",
      "overlap_end": "2026-04-08",
      "severity": "CRITICAL"
    }
  ],
  "summary": {
    "total_conflicts": 1,
    "properties_affected": 1,
    "bookings_involved": 2
  }
}
```

## Design Decisions

- **No new table.** Reads `booking_state` (ACTIVE only). Conflicts computed in-memory.
- **check_out exclusive** — consistent with availability_projection (Phase 126).
- **Severity:** `CRITICAL` ≥ 3 nights, `WARNING` 1-2 nights.
- **Pair deduplication:** (A,B) reported once. `booking_a < booking_b` lexicographically.
- **`itertools.combinations`** used to enumerate all unique pairs per property.
- **Zero write-path changes.** JWT required.

## Files Changed

| File | Change |
|------|--------|
| `src/api/conflicts_router.py` | NEW — GET /conflicts |
| `src/main.py` | MODIFIED — register router + OpenAPI tag |
| `tests/test_conflicts_router_contract.py` | NEW — 39 tests |

## Result

**3205 tests pass** (2 pre-existing SQLite skips). No DB schema changes.
