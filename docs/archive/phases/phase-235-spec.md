# Phase 235 — Multi-Property Conflict Dashboard

**Status:** Closed
**Prerequisite:** Phase 234 — Shift & Availability Scheduler
**Date Closed:** 2026-03-11

## Goal

Managers with multiple properties need a cross-property view of all active booking conflicts. Phase 128 provided per-tenant detection; this phase adds aggregation: grouping by property, severity breakdown, age of oldest conflict, a 4-week timeline, and a heuristic narrative summary.

## Invariant (Phase 235)

`GET /admin/conflicts/dashboard` is **read-only**. It reuses `_find_all_conflicts()` from Phase 128 and adds aggregation in Python. No DB writes. No LLM dependency.

## Design / Files

| File | Change |
|------|--------|
| `src/api/conflicts_router.py` | MODIFIED — added `_compute_dashboard()` helper and `GET /admin/conflicts/dashboard` endpoint |
| `tests/test_conflict_dashboard_contract.py` | NEW — 21 contract tests |
| `docs/archive/phases/phase-235-spec.md` | NEW — this file |

## Endpoint

```
GET /admin/conflicts/dashboard?property_id=&severity=CRITICAL|WARNING
```

**Response:**
- `summary` — total/critical/warning/properties_affected/bookings_involved
- `by_property` — list of property-level aggregations with `oldest_conflict_days`
- `timeline` — last 4 ISO weeks with conflict counts
- `narrative` — heuristic: "3 active conflicts (2 CRITICAL) across 2 properties…"

## Result

**21 tests pass.**
No DB writes. No new tables. Tenant-isolated read on `booking_state`.
