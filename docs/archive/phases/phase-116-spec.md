# Phase 116 — Financial Aggregation API (Ring 1)

**Status:** Closed
**Prerequisite:** Phase 115 (Task Writer)
**Date Closed:** 2026-03-09

## Goal

Implement the Financial Aggregation API (Ring 1) — four read-only endpoints that aggregate `booking_financial_facts` by currency, OTA provider, property, and PaymentLifecycleStatus. Multi-currency aware: amounts in different currencies are never combined. The twelve currencies specified by the system owner are explicitly supported as first-class keys in all responses.

## Invariant

- All four endpoints read from `booking_financial_facts` ONLY — never from `booking_state`
- No mutations: pure read-only aggregation
- Multi-currency invariant: amounts in different currencies MUST NEVER be summed together
- Unsupported currencies are grouped as `"OTHER"` — never silently dropped
- Deduplication: per booking_id, only the most-recent `recorded_at` row is used (BOOKING_AMENDED supersedes BOOKING_CREATED)
- `SUPPORTED_CURRENCIES` is a frozenset — immutable, auditable

## Design / Files

| File | Change |
|------|--------|
| `src/api/financial_aggregation_router.py` | NEW — 4 endpoints + SUPPORTED_CURRENCIES + helpers |
| `src/api/error_models.py` | MODIFIED — added `INVALID_PERIOD` error code |
| `src/main.py` | MODIFIED — `financial_aggregation_router` registered + `financial-aggregation` OpenAPI tag |
| `tests/test_financial_aggregation_router_contract.py` | NEW — 47 tests, Groups A–H |
| `docs/archive/phases/phase-116-spec.md` | NEW — this file |

## Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /financial/summary?period=YYYY-MM` | Gross + commission + net totals per currency |
| `GET /financial/by-provider?period=YYYY-MM` | Per-OTA-provider breakdown per currency |
| `GET /financial/by-property?period=YYYY-MM` | Per-property breakdown per currency |
| `GET /financial/lifecycle-distribution?period=YYYY-MM` | Count by PaymentLifecycleStatus |

## Supported Currencies (Phase 116)

`USD` · `THB` · `EUR` · `GBP` · `CNY` · `INR` · `JPY` · `SGD` · `AUD` · `ILS` · `BRL` · `MXN`

Coverage: North America · Europe · Southeast Asia · UK · China · India · Japan · Singapore · Australia · Israel · Brazil · Mexico

## Result

**2709 tests pass, 2 pre-existing SQLite skips, 3 warnings.**
No booking_state touched. No new DB schema changes.
