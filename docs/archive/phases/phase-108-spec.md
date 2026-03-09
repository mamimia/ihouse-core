# Phase 108 — Financial List Query API

**Status:** Closed
**Prerequisite:** Phase 107 (Roadmap Refresh)
**Date Closed:** 2026-03-09

## Goal

Implement `GET /financial` — a list endpoint for `booking_financial_facts` with optional filters and limit. Parallel to what Phase 106 did for `GET /bookings`.

## Invariant (locked Phase 62+)

This endpoint must NEVER read from or write to `booking_state`.
Reads from `booking_financial_facts` only.

## Design / Files

| File | Change |
|------|--------|
| `src/api/financial_router.py` | MODIFIED — `GET /financial` list endpoint added (Phase 108). Docstring updated. `_MONTH_RE`, `_MAX_LIMIT`, `_DEFAULT_LIMIT` constants added. `list_financial()` async handler. |
| `tests/test_financial_list_router_contract.py` | NEW — 27 tests (1 intentional skip), Groups A–G |

## Endpoint Contract

```
GET /financial
  ?provider=bookingcom   (optional — filter by OTA provider name)
  ?month=YYYY-MM         (optional — filter by calendar month, validated by regex)
  ?limit=50              (optional — clamped to 1–100, default 50)

Auth: Bearer JWT required (tenant_id from sub)
Tenant isolation: .eq("tenant_id", tenant_id) always applied

200 → { tenant_id, count, limit, records: [...] }
400 → VALIDATION_ERROR (bad month format)
403 → (jwt_auth raises)
500 → INTERNAL_ERROR
```

## Test Groups

| Group | What it tests |
|-------|---------------|
| A | 200 success: no filter, provider filter, month filter, both combined, December boundary |
| B | 400 validation: 6 bad month formats + valid format acceptance |
| C | Limit clamping: default 50, below min → 1, above max → 100, valid value |
| D | Tenant isolation: scoped query, other tenant sees empty list |
| E | Auth guard: missing auth → 403 |
| F | Response schema: envelope fields, record fields, count==len(records), no booking_state queries |
| G | Edge cases: empty result → 200, Supabase exception → 500, null fields → null, multi-provider |

## Result

**2401 tests pass, 2 pre-existing SQLite skips, 1 intentional parametrize skip.**
No schema changes. No migrations. `booking_financial_facts` read-only.
