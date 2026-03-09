# Phase 118 — Financial Dashboard API (Ring 2–3)

**Status:** Closed  
**Prerequisite:** Phase 117 — SLA Escalation Engine  
**Date Closed:** 2026-03-09

## Goal

Introduce three read-only Financial Dashboard endpoints building on the Ring 1 aggregation layer (Phase 116). Provide a per-booking status card with lifecycle projection, epistemic tier, and plain-English reason; a RevPAR computation endpoint per property and period; and a lifecycle distribution view grouped by property. All endpoints read exclusively from `booking_financial_facts` and use the shared helpers from `financial_aggregation_router.py`.

## Invariants

- All reads from `booking_financial_facts` ONLY — never `booking_state`
- Deduplication: most-recent `recorded_at` per `booking_id` via `_dedup_latest`
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C
- Worst tier wins in aggregated responses (`_worst_tier`)
- JWT auth required. Tenant isolation enforced at DB query level.

## Design / Files

| File | Change |
|------|--------|
| `src/api/financial_dashboard_router.py` | NEW — GET /financial/status/{booking_id}, GET /financial/revpar, GET /financial/lifecycle-by-property. Exports: `_tier`, `_worst_tier`, `_monetary`, `_project_lifecycle_status` |
| `tests/test_financial_dashboard_router_contract.py` | NEW — 44 tests, Groups A–H |
| `src/main.py` | MODIFIED — registered financial_dashboard_router, added "financial-dashboard" OpenAPI tag |

## Result

**2860 tests pass, 2 pre-existing SQLite skips (unrelated).**  
All three endpoints operational. Shared helpers exported for re-use in Phases 119–120.
