# Phase 84 — Reservation Timeline / Audit Trail

**Status:** Closed
**Prerequisite:** Phase 83 — Vrbo Adapter
**Date Closed:** 2026-03-09

## Goal

Build a unified per-booking audit trail by aggregating events from 4 source tables into a single ordered timeline. Zero DB schema changes — reads only what already exists.

## Module: `reservation_timeline.py`

### Data Structures

| Type | Description |
|---|---|
| `TimelineEvent` (frozen dataclass) | A single event — source_table, event_kind, occurred_at, recorded_at, metadata |
| `ReservationTimeline` (dataclass) | All timeline events for one booking — booking_id, tenant_id, events, partial |

### Sources Aggregated

| Source Table | Events Generated | Tenant-Scoped? |
|---|---|---|
| `event_log` | BOOKING_CREATED / BOOKING_AMENDED / BOOKING_CANCELED | ✅ |
| `booking_financial_facts` | FINANCIAL_RECORDED | ✅ |
| `ota_dead_letter` | DLQ_INGESTED | ❌ global |
| `ota_ordering_buffer` | BUFFERED | ❌ global |

### Public API

```python
build_reservation_timeline(db, tenant_id, booking_id) -> ReservationTimeline
```

- Never raises — partial=True if any source fails
- Events sorted by `recorded_at` ascending (earliest first)
- Empty result is valid (booking not found → empty events list, partial=False)

## Files

| File | Change |
|---|---|
| `src/adapters/ota/reservation_timeline.py` | NEW — TimelineEvent, ReservationTimeline, build_reservation_timeline |
| `tests/test_reservation_timeline_contract.py` | NEW — 45 contract tests (Groups A–H) |

## Result

**812 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
