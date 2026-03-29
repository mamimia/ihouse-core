# Phase 1003 — Canonical Block Classification & Bookings UX

**Status:** Closed
**Prerequisites:** Phase 1002
**Date Closed:** 2026-03-29

## Goal

Harden the booking lifecycle by isolating non-operational "Calendar Blocks" (like iCal placeholders) from real guest reservations. Clean up the Bookings UI to differentiate these sources and guarantee that operational status indicators are reserved for real guests. Replace the fragile popover UI with a durable, viewport-safe Status Guide modal.

## Invariant

- Calendar blocks (`is_calendar_block = true`) must never generate check-in/checkout tasks, never issue guest portal tokens, and never appear in the primary operational bookings table.
- All non-real bookings originating via sync mechanisms must be categorically flagged as `is_calendar_block = true`.
- Status Information Modals must be viewport-safe and natively dismissable in all conditions (Escape, Backdrop).

## Design / Files

| File | Change |
|------|--------|
| `src/api/bulk_import_router.py` | MODIFIED — added provider-agnostic `is_calendar_block` detection to strictly flag calendar block imports. |
| `src/api/bookings_router.py` | MODIFIED — excluded `is_calendar_block = true` automatically from the main API list. Added optional `only_calendar_blocks` query param flag. |
| `ihouse-ui/lib/api.ts` | MODIFIED — added `getCalendarBlocks()` data fetch method for blocks surface. |
| `ihouse-ui/app/(app)/bookings/page.tsx` | MODIFIED — rewrote with dual-surface tabs ("Bookings" & "Calendar Blocks"). Extracted individual rows into `BookingRow` and `CalendarBlockRow`. Added exact-match filter with auto-complete properties. Moved the Status Info Guide from absolute-mounted popover to `position: fixed` viewport-centered modal. |

## Result

**All tests pass.**
Booking and integration layers effectively decouple guest operations from mere availability placehoding.
UI has 0 TypeScript errors. Bookings page runs beautifully. Modal provides safe layout behavior.
