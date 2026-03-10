# Phase 163 — Financial Dashboard UI

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 0 (UI-only phase)  
**Total after phase:** ~4160 passing (unchanged)

## Goal

Build the Financial Dashboard Next.js screen with three sections: summary KPIs, cashflow/payout timeline, and OTA comparison table.

## Deliverables

### New Files
- `ihouse-ui/app/financial/page.tsx` — Financial Dashboard: (1) Summary strip (gross total, commission, net, RevPAR per currency); (2) Cashflow timeline (ISO week bars, forward projection 30/60/90 days); (3) OTA comparison table (net-to-gross ratio, avg commission rate, revenue share per OTA); month picker; currency filter

### Modified Files
- `ihouse-ui/lib/api.ts` — `getFinancialSummary()`, `getCashflow()`, `getOtaComparison()` API methods added
- `ihouse-ui/app/layout.tsx` — Financial nav link (💰) confirmed present

## Key Design Decisions
- OTA comparison renders in a sortable table — ranked by net-to-gross ratio descending by default
- Cashflow forward projection labelled as "estimated" (confidence from Phase 120)
- RevPAR shown per currency with epistemic tier badge (A/B/C colours)
- Month picker changes all three sections simultaneously via shared state
- No Supabase client in any component ✅

## Architecture Invariants Preserved
- UI never reads Supabase directly ✅
- All financial data flows through `/financial/*` FastAPI endpoints ✅
