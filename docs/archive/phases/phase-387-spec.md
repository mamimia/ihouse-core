# Phase 387 — Check-in / Check-out / Maintenance Mobile

**Status:** Closed
**Prerequisite:** Phase 386 (Mobile Ops Command)
**Date Closed:** 2026-03-13

## Goal

Three mobile field-staff pages: check-in (arrivals), check-out (departures), maintenance (filtered tasks with claim/complete flow).

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/checkin/page.tsx` | NEW — Today's arrivals, expandable cards. Confirm action is client-side only (no backend) |
| `ihouse-ui/app/(app)/checkout/page.tsx` | NEW — Today's departures, notes, checkout confirm. Action is client-side only (no backend) |
| `ihouse-ui/app/(app)/maintenance/page.tsx` | NEW — MAINTENANCE tasks, claim→complete flow. Uses real acknowledgeTask/completeTask API |

## Result

TypeScript 0 errors. Maintenance is end-to-end functional. Check-in and check-out read real data but confirm actions are client-side only.
