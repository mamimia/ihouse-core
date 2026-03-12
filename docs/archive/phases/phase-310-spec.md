# Phase 310 — Guest Portal Frontend

**Status:** Closed
**Prerequisite:** Phase 309
**Date Closed:** 2026-03-12

## Goal

Add SSE real-time integration to the guest portal.

## Files

| File | Change |
|------|--------|
| `ihouse-ui/app/guests/page.tsx` | MODIFIED — SSE on bookings channel, 60s auto-refresh |

## SSE Coverage (Phases 307-310)

| Page | Channels | Refresh |
|------|----------|---------|
| Dashboard | bookings, tasks, alerts | SSE + 60s |
| Bookings | bookings | SSE + 60s |
| Financial | financial | SSE + on-demand |
| Tasks | tasks, alerts | SSE + 30s |
| Owner | financial | SSE + 60s |
| Guests | bookings | SSE + 60s |

**Build exit 0, 18 pages.**
