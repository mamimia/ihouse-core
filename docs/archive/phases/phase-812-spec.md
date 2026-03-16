# Phase 812 — PMS Pipeline Proof

**Status:** Closed
**Prerequisite:** Phase 811 (PMS Ingest Pipeline Wiring)
**Date Closed:** 2026-03-16

## Goal

Prove the PMS connector pipeline end-to-end with a mock Guesty server. Fix FK constraint ordering and sync_mode alignment.

## Invariant

- event_log must be written BEFORE booking_state (last_event_id FK constraint)
- sync_mode must be 'api_first' (property_channel_map constraint)

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/pms/normalizer.py` | MODIFIED — fix write order (event_log before booking_state), 28 insertions / 29 deletions |
| `src/api/pms_connect_router.py` | MODIFIED — sync_mode='api_first' |

## Result

**48/48 pipeline proof tests passed.**

7 proofs verified:
1. OAuth2 auth → token received
2. Property discovery → 3 properties
3. Property mapping → property_channel_map
4. Booking fetch → 5 bookings, status mapping correct
5. Normalization → 5 booking_state rows + 5 event_log entries
6. Task automator → PMS creates tasks, iCal suppressed
7. Re-sync → 5 updates (0 new), no duplicates

**Status:** pipeline-proven ✅ | live-PMS-proven: awaits Guesty credentials
