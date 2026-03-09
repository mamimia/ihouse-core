# Phase 87 — Tenant Isolation Hardening

**Status:** Closed
**Prerequisite:** Phase 86 — Conflict Detection Layer
**Date Closed:** 2026-03-09

## Goal

Add a system-level isolation policy layer on top of Phase 81 (query-level audit). Define the canonical table classification (TENANT_SCOPED vs GLOBAL), provide cross-tenant leak detection, and verify the full system is compliant.

## Table Classification

| Table | Scope | Requires tenant_id Filter |
|---|---|---|
| `event_log` | TENANT_SCOPED | ✅ Yes |
| `booking_state` | TENANT_SCOPED | ✅ Yes |
| `booking_financial_facts` | TENANT_SCOPED | ✅ Yes |
| `ota_dead_letter` | GLOBAL | ❌ No (global by design) |
| `ota_ordering_buffer` | GLOBAL | ❌ No (global by design) |

**Rationale for GLOBAL**: `ota_dead_letter` and `ota_ordering_buffer` have no `tenant_id` column. Isolation for these tables is enforced at the application layer via `booking_id` routing.

## Public API

| Function | Returns | Purpose |
|---|---|---|
| `get_table_policy(table_name)` | `TableIsolationPolicy \| None` | Get isolation policy for a single table |
| `get_all_policies()` | `List[TableIsolationPolicy]` | Full policy registry |
| `check_cross_tenant_leak(tenant_a, tenant_b, rows)` | `CrossTenantLeakResult` | Detect cross-tenant row leakage in a result set |
| `audit_system_isolation()` | `SystemIsolationReport` | Full system policy compliance audit |

## Data Structures

| Type | Notes |
|---|---|
| `TableScope` (Enum) | TENANT_SCOPED / GLOBAL |
| `TableIsolationPolicy` (frozen dataclass) | Per-table policy: scope, requires_filter, rationale |
| `CrossTenantLeakResult` (frozen dataclass) | Leak check result: leaked, count, detail |
| `SystemIsolationReport` (frozen dataclass) | Full audit: all_compliant, violations, policies |

## Integration with Phase 81

Phase 81 (`tenant_isolation_checker.py`) audits query configurations.
Phase 87 (`tenant_isolation_enforcer.py`) audits which tables must have those queries.

Together they cover:
- **Query level** (Phase 81): does this query include tenant_id filter?
- **Table level** (Phase 87): should this table require tenant_id filtering?

## Files

| File | Change |
|---|---|
| `src/adapters/ota/tenant_isolation_enforcer.py` | NEW — TABLE_REGISTRY, TableIsolationPolicy, check_cross_tenant_leak, audit_system_isolation |
| `tests/test_tenant_isolation_enforcer_contract.py` | NEW — 54 contract tests (Groups A–I) |

## Result

**974 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
