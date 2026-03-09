# Phase 130 — Properties Summary Dashboard

**Status:** Closed
**Prerequisite:** Phase 129 (Booking Search Enhancement)
**Date Closed:** 2026-03-09

## Goal

Portfolio-level dashboard view showing per-property operational metrics.
Operators can now see their entire property portfolio at a glance without
querying each property individually.

## Endpoint

```
GET /properties/summary?limit=<optional>
```

JWT Bearer required. Reads `booking_state` only.

### Response Shape

```json
{
  "tenant_id": "...",
  "property_count": 3,
  "portfolio": {
    "total_active_bookings": 12,
    "total_canceled_bookings": 2,
    "properties_with_conflicts": 1
  },
  "properties": [
    {
      "property_id": "prop_A",
      "active_count": 5,
      "canceled_count": 1,
      "next_check_in": "2026-04-10",
      "next_check_out": "2026-04-15",
      "has_conflict": true
    },
    ...
  ]
}
```

## Design Decisions

- **No new table.** Reads `booking_state` — groups by `property_id` in Python.
- **`next_check_in` / `next_check_out`**: earliest *upcoming* date (≥ today for check_in, > today for check_out). Past dates excluded.
- **`has_conflict`**: reuses Phase 128's `_has_active_conflict` pattern (`itertools.combinations`).
- **Ordering**: properties sorted by `property_id` (lexicographic, stable).
- **`limit`**: 1–200, default 100. `limit=0` or `limit>200` → 400.
- **`has_conflict` only counts ACTIVE bookings.** CANCELED bookings do not form conflicts.
- Zero write-path changes. JWT required.

## Files Changed

| File | Change |
|------|--------|
| `src/api/properties_summary_router.py` | NEW — GET /properties/summary |
| `src/main.py` | MODIFIED — register router + OpenAPI tag |
| `tests/test_properties_summary_router_contract.py` | NEW — 37 tests |

## Result

**3273 tests pass** (2 pre-existing SQLite skips). No DB schema changes.
