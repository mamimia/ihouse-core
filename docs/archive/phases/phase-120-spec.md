# Phase 120 — Payout Timeline / Cashflow View

**Status:** Closed  
**Prerequisite:** Phase 119 — Reconciliation Inbox API  
**Date Closed:** 2026-03-09

## Goal

Implement an honest cashflow view endpoint (`GET /financial/cashflow?period=YYYY-MM`) that shows operators where money actually stands — not where it is assumed to be. The key differentiator vs. competitors: `OTA_COLLECTING` bookings are explicitly excluded from inflow counts and cannot appear as received payout. Only `PAYOUT_RELEASED` lifecycle status qualifies as confirmed received.

## Invariants

- Reads from `booking_financial_facts` ONLY — never `booking_state`
- Deduplication: most-recent `recorded_at` per `booking_id`
- OTA_COLLECTING bookings are NEVER counted as payout — explicit exclusion, counted in `ota_collecting_excluded_count`
- PAYOUT_RELEASED is the ONLY status counted in `confirmed_released`
- Tenant isolation enforced. JWT auth required.
- `period` param required, YYYY-MM — 400 INVALID_PERIOD on bad/missing
- ISO week keys format: `YYYY-Www` (e.g. `2026-W10`)
- Forward projections are always labeled `confidence: "estimated"`

## Design / Files

| File | Change |
|------|--------|
| `src/api/cashflow_router.py` | NEW — GET /financial/cashflow. Sections: expected_inflows_by_week, confirmed_released, overdue, forward_projection (30/60/90 days), totals. Helper: `_iso_week_key`, `_period_end_date`, `_PENDING_STATUSES`, `_EXCLUDED_FROM_PROJECTION` |
| `tests/test_cashflow_router_contract.py` | NEW — 37 tests, Groups A–L |
| `src/main.py` | MODIFIED — registered cashflow_router, added "cashflow" OpenAPI tag |

## Response Structure

| Section | Content |
|---------|---------|
| `expected_inflows_by_week` | PAYOUT_PENDING + OWNER_NET_PENDING by ISO week and currency |
| `confirmed_released` | PAYOUT_RELEASED only — total + booking_count per currency |
| `overdue` | All pending amounts (no release signal received) per currency |
| `forward_projection` | next_30/60/90_days: booking_count + estimated_revenue + confidence |
| `totals` | Per-currency: total_pending + total_released |
| `ota_collecting_excluded_count` | Count of OTA_COLLECTING bookings explicitly skipped |

## Result

**2860 tests pass, 2 pre-existing SQLite skips (unrelated).**  
Honest exclusion of OTA_COLLECTING verified by Group B tests. ISO week bucketing verified by Group E tests.
