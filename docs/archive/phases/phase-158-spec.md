# Phase 158 — Booking View UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 0 (UI-only phase)  
**Total after phase:** ~4120 passing (unchanged)

## Goal

Build the Bookings List Next.js screen with full filter support (property, status, date range) and a Booking Detail page showing financial facts + amendment history.

## Deliverables

### New Files
- `ihouse-ui/app/bookings/page.tsx` — Bookings list: filter by property_id, status (active/canceled), check_in date range; booking cards showing status chip, dates, OTA provider badge, booking_id
- `ihouse-ui/app/bookings/[id]/page.tsx` — Booking detail: full booking state, financial facts (epistemic tier, lifecycle status), amendment history timeline

### Modified Files
- `ihouse-ui/lib/api.ts` — `getBookings()`, `getBooking(id)`, `getFinancial(bookingId)`, `getAmendments(bookingId)` API methods added
- `ihouse-ui/app/layout.tsx` — Bookings nav link (📋) confirmed present

## Key Design Decisions
- Booking list calls `GET /bookings` with property_id, status, check_in_from, check_in_to query params (Phase 106 + 109)
- Detail page aggregates: `GET /bookings/{id}` + `GET /financial/{id}` + `GET /amendments/{id}`
- Financial epistemic tier A/B/C shown with colour badge (A=green, B=amber, C=red)
- Amendment history shown as a reverse-chronological timeline
- No Supabase client in any component ✅

## Architecture Invariants Preserved
- UI never reads Supabase directly ✅
- Financial data read from `booking_financial_facts` via API — not from `booking_state` ✅
