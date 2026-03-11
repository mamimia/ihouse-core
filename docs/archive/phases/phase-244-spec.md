# Phase 244 — OTA Revenue Mix Analytics API

**Status:** Closed
**Prerequisite:** Phase 243 (Property Performance Analytics API)
**Date Closed:** 2026-03-11

## Goal

All-time OTA revenue mix view — how each channel contributes to gross and net revenue across the entire tenant portfolio. Complements Phase 122 (period-scoped comparison) with an unrestricted time horizon.

## Design

New endpoint: `GET /admin/ota/revenue-mix`

Reads `booking_financial_facts` only. Never reads `booking_state`. Fully standalone router (no cross-router imports from financial_aggregation or financial_dashboard). Deduplication: latest recorded_at per booking_id.

Response: `provider_count`, `total_bookings`, `portfolio_totals` (gross/net by currency), `providers` dict keyed by OTA name, each containing per-currency metrics: `booking_count`, `gross_total`, `commission_total`, `net_total`, `avg_commission_rate`, `net_to_gross_ratio`, `revenue_share_pct`.

## Files

| File | Change |
|------|--------|
| `src/api/ota_revenue_mix_router.py` | NEW — GET /admin/ota/revenue-mix |
| `src/main.py` | MODIFIED — registered ota_revenue_mix_router (Phase 244) |
| `tests/test_ota_revenue_mix_contract.py` | NEW — 41 contract tests (9 groups) |

## Result

**~5,695 tests pass. 0 failures. Exit 0.**
41 new contract tests across 9 groups: shape, empty, single OTA, multi-OTA, ratios, multi-currency, dedup, helpers, route.
