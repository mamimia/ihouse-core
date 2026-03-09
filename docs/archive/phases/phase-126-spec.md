# Phase 126 — Multi-Projection Read Models: Availability Projection

**Status:** Closed
**Prerequisite:** Phase 125 (Hotelbeds Adapter)
**Date Closed:** 2026-03-09

## Goal

Introduce `availability_projection` — the second read model beyond `booking_state`.
Per roadmap: "per-property, per-date occupancy state built from event_log."

Implementation uses `booking_state` (which is itself the projection of `event_log`)
as the authoritative source — consistent with the system's read model hierarchy.

## Design Decisions

- **No new DB table.** Occupancy is computed in-memory on every request.
- **date range semantics:** `[from, to)` — check_in inclusive, check_out exclusive.
- **Only ACTIVE bookings** contribute (CANCELED excluded at DB query level).
- **CONFLICT detection** — two bookings occupying the same date → flagged CONFLICT.
- **Zero write-path changes.** This phase adds a read surface only.
- Foundation for: **channel sync, OTA calendar push, rate management**.

## Endpoint

```
GET /availability/{property_id}?from=<YYYY-MM-DD>&to=<YYYY-MM-DD>
```

### Response Shape
```json
{
  "property_id": "...",
  "from": "2026-04-01",
  "to": "2026-04-11",
  "days": 10,
  "dates": [
    {"date": "2026-04-01", "occupied": false, "booking_id": null, "status": "VACANT"},
    {"date": "2026-04-05", "occupied": true, "booking_id": "bookingcom_R001", "status": "OCCUPIED"},
    {"date": "2026-04-08", "occupied": true, "booking_id": "airbnb_X01", "status": "CONFLICT"}
  ],
  "summary": {"vacant": 7, "occupied": 2, "conflict": 1}
}
```

### Validation
- `from` and `to` are required ISO dates
- `from` must be before `to`
- Maximum range: 366 days

## Files Changed

| File | Change |
|------|--------|
| `src/api/availability_router.py` | NEW — GET /availability/{property_id} |
| `src/main.py` | MODIFIED — register router + OpenAPI tag |
| `tests/test_availability_router_contract.py` | NEW — 36 tests |

## Result

**3129 tests pass** (2 pre-existing SQLite skips).
No DB schema changes. Zero write-path changes.
