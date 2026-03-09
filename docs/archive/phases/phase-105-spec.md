# Phase 105 — Admin Router Phase 82 Contract Tests

**Status:** Closed
**Date Closed:** 2026-03-09

## Goal

Write contract tests for the 4 Phase 82 admin endpoints that had been implemented (in `admin_router.py`) but had zero test coverage. This fills the testing gap without any production source changes.

| Endpoint | Module dependency |
|----------|-----------------|
| `GET /admin/metrics` | `idempotency_monitor.collect_idempotency_report()` |
| `GET /admin/dlq` | `dlq_inspector.{get_pending_count, get_replayed_count, get_rejection_breakdown}()` |
| `GET /admin/health/providers` | `booking_state` + `event_log` DB queries |
| `GET /admin/bookings/{id}/timeline` | `event_log` DB query |

## Invariant

- All tests are **offline** — no live Supabase, no env vars required.
- Admin endpoints are **read-only** — tests verify no writes.
- Tests use `MagicMock` + `unittest.mock.patch` throughout.

## Design / Files

| File | Change |
|------|--------|
| `tests/test_admin_router_phase82_contract.py` | NEW — 41 tests, Groups A–E |

**Group A** (10 tests): `/admin/metrics` — shape, field values, auth, 403  
**Group B** (8 tests): `/admin/dlq` — pending, replayed, breakdown list, auth  
**Group C** (8 tests): `/admin/health/providers` — list structure, status values, ok/unknown, auth  
**Group D** (10 tests): `/admin/bookings/{id}/timeline` — 200, events list, ordering, 404, auth  
**Group E** (5 tests): 500 handling — metrics, dlq, timeline

## Notes

- `/admin/metrics` and `/admin/dlq` both call `_get_supabase_client()` before the injected helper functions — tests must patch both.
- `_get_booking_timeline()` catches all exceptions internally and returns `[]`, so a DB error results in 404 (not 500) — `test_e5` asserts `in (404, 500)` to document this.

## Result

**2346 tests pass, 2 skipped.**
Zero production source changes. Pure test coverage gap filled.
