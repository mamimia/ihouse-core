# Phase 81 — Tenant Isolation Audit

**Status:** Closed
**Prerequisite:** Phase 80 — Structured Logging Layer
**Date Closed:** 2026-03-09

## Goal

Audit all admin/bookings/financial endpoints to verify every DB query is filtered by `tenant_id`.
Add `tenant_isolation_checker.py` as a reusable audit tool with contract tests.

## Audit Findings

| Router | Table | tenant_id Filter | Notes |
|---|---|---|---|
| `bookings_router.py` | `booking_state` | ✅ `.eq("tenant_id", tenant_id)` | |
| `admin_router.py` | `booking_state` (active/canceled/total/last) | ✅ `.eq("tenant_id", tenant_id)` | |
| `admin_router.py` | `booking_financial_facts` (amendments) | ✅ `.eq("tenant_id", tenant_id)` | |
| `admin_router.py` | `ota_dead_letter` (DLQ) | ⚠️ Global — intentional | `ota_dead_letter` has no `tenant_id` column — documented in docstring |
| `financial_router.py` | `booking_financial_facts` | ✅ `.eq("tenant_id", tenant_id)` | |

**All tenant-scoped tables are correctly filtered. DLQ is explicitly global.**

## Inconsistency Fixed

`financial_router.py` 404 and 500 responses used raw `JSONResponse({"error": "..."})` instead of
the Phase 75 standard `make_error_response` with `{"code": "..."}`. Fixed in this phase.

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/tenant_isolation_checker.py` | NEW — `TenantIsolationReport`, `audit_tenant_isolation()`, `check_query_has_tenant_filter()` |
| `tests/test_tenant_isolation_checker_contract.py` | NEW — 24 contract tests (Groups A–D) |
| `src/api/financial_router.py` | MODIFIED — 404/500 now use `make_error_response` |
| `tests/test_financial_router_contract.py` | MODIFIED — T2/T7 assertions updated: `error` → `code` |

## Invariant

- `tenant_isolation_checker.py` is a pure audit tool — never reads DB, never writes DB
- Never raises (conservative: errors counted as unfiltered)
- `TenantIsolationReport` is frozen (immutable)

## Result

**687 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
