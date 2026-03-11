# Phase 243 — Property Performance Analytics API

**Status:** Closed
**Prerequisite:** Phase 242 (Booking Lifecycle State Machine Visualization API)
**Date Closed:** 2026-03-11

## Goal

Combine booking_state (counts + top provider) with booking_financial_facts (revenue) into a property-level performance analytics endpoint — giving managers a holistic view of each property's booking volume AND revenue health in a single response.

## Design

New endpoint: `GET /admin/properties/performance`

Reads two sources:
- `booking_state` — active/canceled counts per property, top_provider
- `booking_financial_facts` — deduplicated (latest recorded_at per booking_id) gross/net revenue per currency

No new tables or migrations. Read-only. Extends Phase 130 (operational) with Phase 116 financial data.

Response: `property_count`, `portfolio_totals` (aggregate revenue + counts), `properties` sorted by active_bookings descending. Each property: `active_bookings`, `canceled_bookings`, `cancellation_rate_pct`, `total_gross_revenue`, `total_net_revenue`, `avg_booking_value` (all per-currency dicts), `top_provider`.

## Files

| File | Change |
|------|--------|
| `src/api/property_performance_router.py` | NEW — GET /admin/properties/performance |
| `src/main.py` | MODIFIED — registered property_performance_router (Phase 243) |
| `tests/test_property_performance_contract.py` | NEW — 35 contract tests (8 groups) |

## Result

**~5,654 tests pass. 0 failures. Exit 0.**
35 new contract tests across 8 groups: shape, empty, state counts, revenue, portfolio totals, dedup, pure helpers, route registration.
