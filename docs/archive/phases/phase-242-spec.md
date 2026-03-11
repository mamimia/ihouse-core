# Phase 242 — Booking Lifecycle State Machine Visualization API

**Status:** Closed
**Prerequisite:** Phase 241 (Booking Financial Reconciliation Dashboard API)
**Date Closed:** 2026-03-11

## Goal

Expose a cross-provider state machine snapshot — how bookings are distributed across the lifecycle (active/canceled), per OTA provider, plus transition event volumes (CREATED/AMENDED/CANCELED counts) and derived rates.

## Design

New endpoint: `GET /admin/bookings/lifecycle-states`

Reads two sources:
- `booking_state` — current status per booking (active / canceled)
- `event_log` — transition event counts (BOOKING_CREATED, BOOKING_AMENDED, BOOKING_CANCELED)

No new tables or migrations. Read-only.

Response fields: `total_bookings`, `state_distribution`, `by_provider` (sorted worst-first), `transition_counts`, `amendment_rate_pct`, `cancellation_rate_pct`.

## Files

| File | Change |
|------|--------|
| `src/api/booking_lifecycle_router.py` | NEW — GET /admin/bookings/lifecycle-states |
| `src/main.py` | MODIFIED — registered booking_lifecycle_router (Phase 242) |
| `tests/test_booking_lifecycle_contract.py` | NEW — 32 contract tests (8 groups) |

## Result

**~5,619 tests pass. 0 failures. Exit 0.**
32 new contract tests (8 groups: shape, empty, state distribution, by-provider, transitions, rates, edge cases, auth).
