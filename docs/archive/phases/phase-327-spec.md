# Phase 327 — Availability Broadcaster Integration Tests

**Status:** Closed
**Prerequisite:** Phase 326 (State Transition Guard)
**Date Closed:** 2026-03-12

## Goal

Integration tests for `broadcast_availability()` — the IPI proactive availability broadcast pipeline.

## Files Changed

| File | Change |
|------|--------|
| `tests/test_availability_broadcast_integration.py` | NEW — 10 tests |

## Test Coverage

| Group | Tests | What |
|-------|-------|------|
| A — PROPERTY_ONBOARDED | 3 | Single booking+channel, no bookings, no channels |
| B — CHANNEL_ADDED | 2 | Target new provider, source provider excluded |
| C — Failure Isolation | 2 | Executor error → bookings_failed, DB bootstrap error |
| D — Report Shape | 3 | serialise_broadcast_report, per-booking entries, bookings_found |

## Result

**10 tests. 10 passed. 0 failed. 0.22s. Exit 0.**
