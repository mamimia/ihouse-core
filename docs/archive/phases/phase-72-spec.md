# Phase 72 — Tenant Summary Dashboard

**Status:** Closed
**Prerequisite:** Phase 71 (Booking State Query API)
**Date Closed:** 2026-03-09

## Goal

Expose a real-time operational dashboard endpoint per tenant. Before this phase, an operator had no single read endpoint to understand system health for a tenant — they'd need to query Supabase directly.

## API Contract

```
GET /admin/summary
Authorization: Bearer <JWT>

200 → {
  tenant_id:         str
  active_bookings:   int   ← booking_state WHERE status='active'
  canceled_bookings: int   ← booking_state WHERE status='canceled'
  total_bookings:    int   ← all booking_state rows
  dlq_pending:       int   ← ota_dead_letter WHERE replay_result not APPLIED (global)
  amendment_count:   int   ← booking_financial_facts WHERE event_kind='BOOKING_AMENDED'
  last_event_at:     str|null  ← most recent booking_state.updated_at
}
403 → AUTH_FAILED
500 → { error: "INTERNAL_ERROR" }
```

## Files

| File | Change |
|------|--------|
| `src/api/admin_router.py` | NEW — GET /admin/summary |
| `src/main.py` | MODIFIED — admin tag + admin_router |
| `tests/test_admin_router_contract.py` | NEW — 14 contract tests |

## Invariants

- All booking_state queries tenant-scoped via `.eq("tenant_id", tenant_id)`
- DLQ count is global (ota_dead_letter has no tenant_id) — shared infra metric
- Read-only. Zero writes
- 500 swallows exceptions without leaking details

## Result

**481 tests pass, 2 skipped.**
No schema changes. No new migrations.
