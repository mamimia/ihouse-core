# Phase 386 — Mobile Ops Command Surface

**Status:** Closed
**Prerequisite:** Phase 385 (Checkpoint B)
**Date Closed:** 2026-03-13

## Goal

Mobile-first operational command view for operations managers. Shows critical tasks, SLA risk, arrivals, departures with real data from GET /tasks and GET /bookings.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/ops/page.tsx` | NEW — 550 lines, stat grid, task feed, booking rows |

## Result

TypeScript 0 errors. Data reads from real backend endpoints (getTasks, getBookings).
