# Phase 160 — Guest Profile UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 0 (UI-only phase)  
**Total after phase:** ~4140 passing (unchanged)

## Goal

Build the Guest Profile Next.js view linked from the Booking Detail page (Phase 158), allowing managers to view and update guest pre-arrival data.

## Deliverables

### Modified Files
- `ihouse-ui/app/bookings/[id]/page.tsx` — Guest profile panel added to booking detail; calls `getGuest(bookingId)`, shows name/phone/email/arrival_time/readiness_status; "Edit" inline form to patch guest profile
- `ihouse-ui/lib/api.ts` — `getGuest(bookingId)`, `upsertGuest(data)`, `patchGuest(bookingId, data)` API methods added

## Key Design Decisions
- Guest profile is linked from inside the Booking Detail screen — not a standalone route
- Readiness status shown as a colour badge: ready=green, pending=amber, issue=red
- Graceful empty state when no profile exists yet (POST to create on first save)
- No auth required for profile editing beyond existing JWT (tenant isolation via token)

## Architecture Invariants Preserved
- UI never reads Supabase directly ✅
- Guest profile writes go through `/guests` API — never direct DB ✅
