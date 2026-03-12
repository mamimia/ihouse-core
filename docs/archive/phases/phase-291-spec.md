# Phase 291 — Financial Dashboard UI (Live)

**Date:** 2026-03-12
**Category:** 🎨 Frontend

## Objective

Extend the Financial Dashboard with an OTA mix visualization and owner-statement navigation.

## Audit Finding

`ihouse-ui/app/financial/page.tsx` was already 870 lines with 5 complete sections (Phases 163-191):
- Section 0: Portfolio Overview (multi-currency rows with bars)
- Section 1: Summary Bar (gross / commission / net / bookings)
- Section 2: By OTA Provider (table with commission ratios)
- Section 3: By Property (table)
- Section 4: Lifecycle Distribution bar (7 payment states)
- Section 5: Reconciliation Inbox with drill-down link

## Changes

### `ihouse-ui/app/financial/page.tsx` — MODIFIED
- **Section 1.5: OTA Mix SVG Donut** (NEW) — inline-computed SVG pie chart with branded colours per OTA (Airbnb red, Booking.com navy, Expedia, VRBO…), center label "N OTAs", legend with %-share. Conditionally rendered when ≥2 providers exist.
- **Owner Statements link** (NEW) — quick-nav card at bottom → `/financial/statements`
- Header comment bumped to `Phase 291`

### `ihouse-ui/lib/api.ts` — MODIFIED
- Added `getCashflowProjection(period, baseCurrency?)` → `GET /cashflow/projection`
- Added `CashflowProjectionResponse` and `CashflowWeek` interfaces

## Verification

- TypeScript: `tsc --noEmit` → 0 errors
- Python: 6,216 passed · 0 failed · exit 0
