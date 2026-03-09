# Phase 122 — OTA Financial Health Comparison

**Status:** Closed
**Prerequisite:** Phase 121 (Owner Statement Generator)
**Date Closed:** 2026-03-09

## Goal

Provide operators with a per-OTA financial health view to support smarter channel
management decisions. The endpoint aggregates `booking_financial_facts` per OTA provider
and computes:

- Average commission rate per OTA (ota_commission / total_price × 100)
- Net-to-gross ratio per OTA (net_to_property / total_price)
- Lifecycle distribution per OTA (which OTAs have more RECONCILIATION_PENDING?)
- Revenue share by OTA (each OTA's gross as % of total gross)
- Booking count per OTA

All per currency — no cross-currency arithmetic ever performed.
Epistemic tier (A/B/C) on every metric. Worst tier wins per OTA.

## Invariant (if applicable)

- Reads from `booking_financial_facts` ONLY — never `booking_state` (Phase 116).
- Multi-currency: no cross-currency aggregation. Each currency bucket is independent.
- Deduplication: most-recent `recorded_at` per `booking_id` (Phase 116 dedup rule).
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins per OTA.
- Bookings where total_price=0 or None excluded from ratio calculations.
- Tenant isolation enforced at DB level.

## Design / Files

| File | Change |
|------|--------|
| `src/api/ota_comparison_router.py` | NEW — GET /financial/ota-comparison?period= |
| `src/main.py` | MODIFIED — register ota_comparison_router |
| `tests/test_ota_comparison_router_contract.py` | NEW — contract tests Groups A–H, ~40 tests |
| `docs/archive/phases/phase-122-spec.md` | NEW (this file) |

## Result

**~2950 tests pass, 2 pre-existing SQLite skips.**
No DB schema changes. All reads from `booking_financial_facts` only.
