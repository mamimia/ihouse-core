# Phase 371 — Booking Search Full-Text Enhancement

**Status:** Closed  
**Date Closed:** 2026-03-12

## Goal

Add free-text search capability to the booking list endpoint.

## Files Modified

| File | Change |
|------|--------|
| `src/api/bookings_router.py` | MODIFIED — Added `q` query parameter; uses Supabase `or_` with `ilike` across booking_id, reservation_ref, guest_name |

## Result

Tests: all booking tests passing. No regressions.
