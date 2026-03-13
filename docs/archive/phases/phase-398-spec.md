# Phase 398 — Checkin + Checkout Backend

**Status:** Closed
**Prerequisite:** Phase 397 (JWT Role Claim)
**Date Closed:** 2026-03-13

## Goal

Implement real backend endpoints for guest checkin and checkout operations. Checkout auto-creates a CLEANING task. Eliminated UI deception where buttons were frontend-only.

## Invariant

Booking state machine: active → checked_in → checked_out. No further transitions. Idempotent.

## Design / Files

| File | Change |
|------|--------|
| `src/api/booking_checkin_router.py` | NEW — POST /bookings/{id}/checkin + /checkout |
| `tests/test_booking_checkin_checkout.py` | NEW — 10 contract tests |
| `src/main.py` | MODIFIED — router registration |

## Result

**10 tests pass, 0 skipped.**
