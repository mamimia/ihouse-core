# Phase 75 — Production Hardening: API Error Standards + Response Headers

**Status:** Closed
**Prerequisite:** Phase 74 (Date Normalization)
**Date Closed:** 2026-03-09

## Problem Solved

Before this phase, error responses across the API had inconsistent shapes:
- `{"error": "BOOKING_NOT_FOUND", "booking_id": "..."}` (bookings_router)
- `{"error": "INTERNAL_ERROR"}` (admin_router)
- No `message` field (hard for API consumers to display errors)
- No `trace_id` (impossible to correlate client errors to server logs)
- No `X-API-Version` header (consumers can't detect version without parsing headers)

## Solution

### `src/api/error_models.py` (NEW)
Standard error response helper used by all Phase 71+ routers:

```json
{
  "code":     "BOOKING_NOT_FOUND",
  "message":  "Booking not found for this tenant",
  "trace_id": "uuid-from-middleware"
}
```

### `src/main.py` (MODIFIED)
Middleware now adds `X-API-Version: {app.version}` on every response (alongside existing `X-Request-ID`).

### `src/api/bookings_router.py` + `src/api/admin_router.py` (MODIFIED)
Use `make_error_response()` — responses now have `code`, `message`, optional `trace_id`.

## Backward Compatibility

- `financial_router.py` and `webhooks.py` keep legacy `{"error": "..."}` format
- No schema changes. No migrations.

## Files

| File | Change |
|------|--------|
| `src/api/error_models.py` | NEW — `ErrorCode` + `make_error_response()` |
| `src/main.py` | MODIFIED — `X-API-Version` header in middleware |
| `src/api/bookings_router.py` | MODIFIED — standard error format |
| `src/api/admin_router.py` | MODIFIED — standard error format |
| `tests/test_api_error_standards_contract.py` | NEW — 19 contract tests |
| `tests/test_bookings_router_contract.py` | UPDATED — `code` not `error` |
| `tests/test_admin_router_contract.py` | UPDATED — `code` not `error` |

## Result

**533 tests pass, 2 skipped.**
