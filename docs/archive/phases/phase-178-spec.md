# Phase 178 — Worker Mobile UI (/worker route)

**Status:** Closed  
**Prerequisite:** Phase 177 (SLA→Dispatcher Bridge)  
**Date Closed:** 2026-03-10

## Goal

Create a dedicated mobile-first route `/worker` for field workers (cleaners, maintenance, check-in staff). Unlike `/tasks` (manager-facing list), this is the worker's primary app: a full-screen, bottom-nav, tap-to-act interface with acknowledge + complete + report-issue flows.

## What `/tasks` already has (Phase 157)
- List, filter, acknowledge, SLA countdown, overdue badge, polling

## What `/worker` adds
- **Complete action** — ACKNOWLEDGED/IN_PROGRESS → COMPLETED with notes
- **Report Issue** — routes to a simple form (message sent to ops)  
- **Bottom navigation** — no sidebar (mobile-native feel)
- **Per-task detail sheet** — full property info, booking_id, notes history
- **Role/date filter** pre-applied from query params

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/worker/page.tsx` | NEW — full mobile UI |
| `ihouse-ui/lib/api.ts` | MODIFIED — add `completeTask(id, notes)` if missing |

## Result

**TBD.**
