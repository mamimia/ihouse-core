# Phase 103 — Payment Lifecycle Query API

**Status:** Closed
**Prerequisite:** Phase 93 (Payment Lifecycle / Revenue State Projection)
**Date Closed:** 2026-03-09

## Goal

Expose `explain_payment_lifecycle()` (Phase 93) via HTTP. New `GET /payment-status/{booking_id}` endpoint. Reads the **most recent** `booking_financial_facts` record for the booking (`ORDER BY recorded_at DESC LIMIT 1`), calls `explain_payment_lifecycle()` in-memory, returns the projected `PaymentLifecycleState` plus `rule_applied` and `reason` from `PaymentLifecycleExplanation`. Follows the same pattern as `financial_router.py` (Phase 67) and `owner_statement_router.py` (Phase 101).

## Invariant

- Never reads `booking_state`. Tenant isolation at DB level (`.eq("tenant_id", tenant_id)`).
- `explain_payment_lifecycle()` is pure (no IO, no writes).
- `booking_state` must NEVER contain financial calculations (Phase 62+ invariant upheld).

## Design / Files

| File | Change |
|------|--------|
| `src/api/payment_status_router.py` | NEW — `GET /payment-status/{booking_id}`; JWT auth; `BOOKING_NOT_FOUND` 404; 500 on DB error; uses `explain_payment_lifecycle()` not `project_payment_lifecycle()` |
| `src/main.py` | MODIFIED — `payment_status_router` registered; `"payment-status"` tag added |
| `tests/test_payment_status_router_contract.py` | NEW — 24 tests, Groups A–E (happy path, 404, auth, lifecycle status, tenant isolation + 500) |

## Notes

- **`RECONCILIATION_PENDING`** (not `CANCELED_*`) is the status for `BOOKING_CANCELED` events per Phase 93 `canceled_booking` rule — test d2 documents this behaviour.
- Uses `explain_payment_lifecycle()` not `project_payment_lifecycle()` to expose `rule_applied` and `reason` for diagnostic transparency.

## Result

**2285 tests pass, 2 skipped.**
No Supabase schema changes. No migrations. No `booking_state` reads or writes.
