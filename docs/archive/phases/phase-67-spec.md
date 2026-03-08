# Phase 67 — Financial Facts Query API

**Status:** Closed
**Prerequisite:** Phase 66 (booking_financial_facts Supabase table)
**Date Closed:** 2026-03-09

## Goal

Expose `booking_financial_facts` Supabase data via a read-only REST endpoint.

## Invariant

This endpoint reads from `booking_financial_facts` ONLY. It must NEVER read from or write to `booking_state`.

## New File: `src/api/financial_router.py`

```
GET /financial/{booking_id}
  → jwt_auth (Bearer JWT, sub = tenant_id)
  → .eq("booking_id", booking_id).eq("tenant_id", tenant_id)
  → ORDER BY recorded_at DESC LIMIT 1
  → 200 { booking_id, tenant_id, provider, total_price, ... }
  → 404 { "error": "BOOKING_NOT_FOUND" }
  → 403 if JWT missing/invalid
  → 500 INTERNAL_ERROR (no internals leaked)
```

## Modified: `src/main.py`

Added `financial` tag. Registered `financial_router`.

## New: `tests/test_financial_router_contract.py` — 8 tests

| # | Test |
|---|------|
| T1 | Valid booking → 200 + correct fields |
| T2 | Unknown booking → 404 |
| T3 | No auth → 403 |
| T4 | Other tenant's booking → 404 (isolation) |
| T5 | Multiple rows → most recent returned |
| T6 | Response schema has all required fields |
| T7 | Supabase error → 500, no internal details leaked |
| T8 | tenant_id passed correctly to Supabase query |

## Result

**396 tests pass, 2 skipped** (was 388).
