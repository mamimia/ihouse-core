# Phase 170 — Owner Portal UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 0 (UI-only phase)  
**Total after phase:** 4420 passing (unchanged)

## Goal

Build the Owner Portal Next.js screen — a trust-based, financially clear surface for property owners showing portfolio summary, monthly statements with line items, and payout timeline.

## Deliverables

### New Files
- `ihouse-ui/app/owner/page.tsx` — Owner Portal: (1) Portfolio summary header — total properties managed, total bookings, gross revenue, owner net (aggregated across properties); (2) Property cards — gross/commission/net per property, booking count, "Statement →" link opens slide-out drawer; (3) Statement drawer — summary table + per-booking line items with epistemic tier badges (A/B/C), month picker; (4) Payout timeline section — link to Financial Dashboard cashflow view

### Modified Files
- `ihouse-ui/lib/api.ts` — `OwnerStatement`, `StatementEntry` types; `getOwnerStatement(propertyId, month, mgmtFeePct)` API method added
- `ihouse-ui/app/layout.tsx` — Owner Portal nav link (🏠) added

## Key Design Decisions
- Portfolio summary aggregates across all properties for the same tenant (multiple `GET /owner-statement` calls)
- Statement drawer is scoped to one property + one month at a time
- Epistemic tier badges per booking line: A (green) = FULL confidence, B (amber) = PARTIAL, C (red) = ESTIMATED
- OTA_COLLECTING bookings shown greyed-out with "pending payout" label
- Owner portal shows no operational data (no tasks, no alerts) — trust and clarity first

## Architecture Invariants Preserved
- UI never reads Supabase directly ✅
- All financial data flows through `/owner-statement/{property_id}` FastAPI endpoint ✅
