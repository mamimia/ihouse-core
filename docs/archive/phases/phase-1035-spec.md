# Phase 1035 — OM-1: Stream Redesign

**Status:** Closed
**Prerequisite:** Phase 1034 (OM-1: Manager Task Intervention Model)
**Date Closed:** 2026-04-01

## Goal

Migrate the Operational Manager Stream away from the historical `audit_events` table and onto live operational data sources: the `tasks` table (live queue) and `bookings` table (confirmed stay window). Remove the stale Sessions tab. Fix the property name resolution bug that caused raw bigint IDs to appear instead of human names.

## Invariant

- Stream data source is always live `tasks` + `bookings`, never `audit_events`.
- Property name resolution uses `properties.property_id` (text code), never `properties.id` (bigint).
- Sessions tab does not exist in OM Stream — removed as confusing and redundant.

## Design / Files

| File | Change |
|------|--------|
| `src/api/task_takeover_router.py` | NEW `GET /manager/tasks` — live operational task queue, urgency sort (overdue→today→upcoming→future) |
| `src/api/task_takeover_router.py` | NEW `GET /manager/stream/bookings` — yesterday → +7d window, confirmed stays only |
| `ihouse-ui/app/(app)/manager/stream/page.tsx` | MODIFIED — Stream migrated to live data sources; Sessions tab removed; property name resolution fixed |
| `src/api/permissions_router.py` | MODIFIED — `ReassignPanel` empty state fixed: human-readable message, not raw `.` string |

## Result

Backend-proven via DB SQL proofs. UI visual proof deferred (pending next session with live staging access).
Property name resolution bug fixed: backend was joining `properties.id` (bigint PK) instead of `properties.property_id` (text code), causing raw numbers to appear in all manager surfaces.
