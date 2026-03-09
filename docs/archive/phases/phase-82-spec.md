# Phase 82 — Admin Query API

**Status:** Closed
**Prerequisite:** Phase 81 — Tenant Isolation Audit
**Date Closed:** 2026-03-09

## Goal

Extend `admin_router.py` with 4 operator-facing query endpoints:
- `GET /admin/metrics` — idempotency + DLQ health metrics
- `GET /admin/dlq` — DLQ pending/replayed breakdown
- `GET /admin/health/providers` — per-provider last ingest status
- `GET /admin/bookings/{id}/timeline` — per-booking event history from event_log

## Design

| Endpoint | Source | Tenant-Scoped |
|---|---|---|
| `GET /admin/metrics` | `idempotency_monitor.collect_idempotency_report()` | ❌ global (DLQ) |
| `GET /admin/dlq` | `dlq_inspector.get_pending/replayed/breakdown()` | ❌ global (DLQ) |
| `GET /admin/health/providers` | `event_log` query per provider | ✅ |
| `GET /admin/bookings/{id}/timeline` | `event_log` filtered by tenant + booking_id | ✅ |

All endpoints:
- JWT auth required
- Read-only — never write to any table
- 404 uses `make_error_response(code=BOOKING_NOT_FOUND)`
- 500 uses `make_error_response(code=INTERNAL_ERROR)`
- `_get_booking_timeline` and `_get_provider_health` swallow internal exceptions (conservative: return empty)

## Files

| File | Change |
|---|---|
| `src/api/admin_router.py` | MODIFIED — added 4 endpoints + 2 helper functions |
| `tests/test_admin_query_api_contract.py` | NEW — 35 contract tests (Groups A–E) |

## Invariant

- `event_log` is read-only — all queries are SELECT only
- DLQ is global — ota_dead_letter has no tenant_id, documented in docstrings

## Result

**722 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
