# Phase 101 — Owner Statement Query API

**Status:** Closed
**Prerequisite:** Phase 100 (Owner Statement Foundation)
**Date Closed:** 2026-03-09

## Goal

Expose `build_owner_statement()` (Phase 100) via HTTP. New `GET /owner-statement/{property_id}?month=YYYY-MM` endpoint. Reads from `booking_financial_facts`, assembles `BookingFinancialFacts` objects, calls `build_owner_statement()` in-memory, returns serialized `OwnerStatementSummary`. Follows the exact same pattern as Phase 67 (Financial Facts Query API) and Phase 71 (Booking State Query API).

## Invariant

- Tenant isolation: `.eq("tenant_id", tenant_id)` at DB query level — same as all other API routers.
- No `booking_state` reads. No writes of any kind.
- `booking_state` must NEVER contain financial calculations (Phase 62+ invariant upheld).

## Design / Files

| File | Change |
|------|--------|
| `src/api/owner_statement_router.py` | NEW — `GET /owner-statement/{property_id}?month=YYYY-MM`; JWT auth; month regex validation (`YYYY-MM`); `INVALID_MONTH` 400; `PROPERTY_NOT_FOUND` 404; 500 on DB error; entries serialized with `Decimal → str` |
| `src/api/error_models.py` | MODIFIED — `PROPERTY_NOT_FOUND` and `INVALID_MONTH` added to `ErrorCode` class and `_DEFAULT_MESSAGES` |
| `src/main.py` | MODIFIED — `owner_statement_router` registered; `"owner-statement"` tag added to `_TAGS` |
| `tests/test_owner_statement_router_contract.py` | NEW — 28 tests, Groups A–E (happy path, 404, auth, validation, tenant isolation + 500 handling) |

## Result

**2162 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations. No `booking_state` writes.
