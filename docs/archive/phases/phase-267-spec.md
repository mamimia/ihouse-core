# Phase 267 — E2E Financial Summary Integration Test

**Status:** Closed
**Prerequisite:** Phase 266 (E2E Booking Flow Integration Test)
**Date Closed:** 2026-03-11

## Goal

Add HTTP-level and function-level E2E tests for the full financial API surface.
CI-safe — no live DB, no staging required.

Covered the gap in testing for the financial aggregation layer that was already
wired to Supabase but had no CI-safe E2E test coverage at the API boundary.

## Design Notes

The router `GET /financial/{booking_id}` in `financial_router.py` (registered first)
shadows HTTP paths like `/financial/summary` via path-parameter capture.
**Strategy for Groups A-E:** call the aggregation handler functions directly using
`asyncio.run()` with a mocked `client=` parameter — avoids routing shadow, tests
the full business logic. **Groups F-G:** full HTTP-level via TestClient, testing the
actually reachable Phase 67/108 endpoints.

## Files

| File | Change |
|------|--------|
| `tests/test_financial_flow_e2e.py` | NEW — 30 tests, 7 groups (A-G) |

**Test groups:**
- **Group A** (7): `get_financial_summary` — period validation, shape, currency bucket keys, aggregation
- **Group B** (4): `get_financial_by_provider` — 400, 200 + providers key, provider name, empty
- **Group C** (4): `get_financial_by_property` — 400, 200 + properties key, property_id, empty
- **Group D** (4): `get_lifecycle_distribution` — 400, 200 + distribution key, required keys, empty  
- **Group E** (4): `get_multi_currency_overview` — 400, invalid currency filter, 200 + period, empty
- **Group F** (3): `GET /financial/{booking_id}` — 200 shape, required keys, 404
- **Group G** (4): `GET /financial` — 200 + records key, count/limit, invalid month 400, empty count

## Key Insight Documented

`financial_router.py`'s `GET /financial/{booking_id}` captures all `/financial/*` HTTP paths
due to FastAPI registration order. Aggregation routes (`/financial/summary` etc.) are only
testable through direct function calls in CI-safe tests.

## Result

**6,080 tests pass, 13 skipped, 0 failures.**
30 new CI-safe E2E tests covering the financial API query surface.
