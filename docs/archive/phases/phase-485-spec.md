# Phase 485 — Guest Profile Hydration Pipeline

**Status:** Closed
**Prerequisite:** Phase 484 (Platform Checkpoint XXII)
**Date Closed:** 2026-03-14

## Goal

Enable retroactive guest profile extraction from existing event_log BOOKING_CREATED
events, filling the gap between 1516 bookings and 0 guest profiles.

## Design / Files

| File | Change |
|------|--------|
| `src/services/guest_profile_backfill.py` | NEW — backfill service: scans event_log, batch-upserts to guest_profile |
| `src/api/guest_profile_router.py` | MODIFIED — added POST /guests/backfill endpoint |
| `tests/test_guest_profile_backfill.py` | NEW — 10 tests (extractor, backfill service, API endpoint) |
| Supabase migration | NEW — UNIQUE constraint on guest_profile(booking_id, tenant_id) |

## Result

**10 tests pass, 0 failed.**
Backfill endpoint supports dry_run mode and batch_size configuration.
