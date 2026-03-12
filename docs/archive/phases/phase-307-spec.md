# Phase 307 — Frontend Real Data Integration (Dashboard + Bookings)

**Status:** Closed
**Prerequisite:** Phase 306 (Real-Time Event Bus)
**Date Closed:** 2026-03-12

## Goal

Connect the dashboard and bookings UI pages to real API endpoints with typed fetch, SSE real-time updates, auto-refresh, and proper error handling.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/dashboard/page.tsx` | MODIFIED — added SSE integration for real-time refresh |
| `ihouse-ui/app/bookings/page.tsx` | MODIFIED — replaced raw fetch with typed api.getBookings(), added SSE, auto-refresh, live banner |
| `ihouse-ui/lib/api.ts` | MODIFIED — added source param to getBookings() |

## Key Changes

1. **Dashboard SSE**: subscribes to bookings/tasks/alerts channels, auto-refreshes on real events
2. **Bookings rewrite**: raw `fetch('/api/bookings')` → typed `api.getBookings()` with auto auth headers, 401/403 auto-logout
3. **Bookings SSE**: subscribes to bookings channel, shows live event banner, auto-refreshes
4. **Bookings UX**: refresh button, last-refresh timestamp, 60s auto-timer

## Result

**Next.js build exit 0, 18 pages compile. 0 new backend tests (frontend-only phase).**
