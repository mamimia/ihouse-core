# Phase 164 — Owner Statement UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 0 (UI-only phase)  
**Total after phase:** ~4160 passing (unchanged)

## Goal

Build the Owner Statement Next.js screen with a monthly statement view showing per-booking line items, management fee deduction, and owner net total. Available under `/financial/statements`.

## Deliverables

### New Files
- `ihouse-ui/app/financial/statements/page.tsx` — Owner Statement page: property selector, month picker, statement table (check-in, check-out, OTA, gross, commission, net_to_property, epistemic tier badge per row), management fee row, owner_net_total footer, PDF export button (calls `GET /owner-statement/{property_id}?format=pdf`)

### Modified Files
- `ihouse-ui/lib/api.ts` — `getOwnerStatement(propertyId, month, mgmtFeePct)` API method added
- `ihouse-ui/app/layout.tsx` — No new nav link (accessible from Financial nav)

## Key Design Decisions
- PDF export calls the existing Phase 121 PDF endpoint (`format=pdf`) — downloads directly from browser
- Management fee percentage input: defaults to 10%, editable inline (re-fetches statement on change)
- Epistemic tier badge per booking line: A (green) / B (amber) / C (red)
- OTA_COLLECTING bookings shown with a "Pending payout" label and greyed-out net figure
- No Supabase client in any component ✅

## Architecture Invariants Preserved
- UI never reads Supabase directly ✅
- Owner statement data comes entirely from `/owner-statement/{property_id}` FastAPI endpoint ✅
