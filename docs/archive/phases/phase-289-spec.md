# Phase 289 — Booking Management UI (Live)

**Date:** 2026-03-12
**Category:** 🎨 Frontend

## Objective

Connect booking pages to all three booking endpoints and expose booking history types in shared API client.

## Audit Finding

Both booking pages were already fully built (Phases 158-194):
- `/bookings` — list with 4 filters (property, status, OTA source, check-in date range), table with skeleton loading, click-to-detail navigation
- `/bookings/[id]` — 5-tab detail view (Overview, Sync Log, Tasks, Financial, History) + Guest Link panel

## Changes

### `ihouse-ui/lib/api.ts` — MODIFIED
- Added `getBookingHistory(booking_id)` → `GET /booking-history/{id}`
- Added `getBookingAmendments(booking_id)` → `GET /bookings/{id}/amendments`
- Added `getBookingFinancial(booking_id)` → `GET /financial/{id}`
- Added `BookingHistoryEntry`, `BookingAmendment`, `BookingFinancialDetail` interfaces

### `ihouse-ui/app/bookings/[id]/page.tsx` — MODIFIED
- Header comment bumped to `Phase 289`

## Verification

- TypeScript: `tsc --noEmit` → 0 errors
- Python test suite: 6,216 passed · 0 failed · exit 0
