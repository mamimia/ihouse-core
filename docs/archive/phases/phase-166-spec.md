# Phase 166 — Worker + Owner Role Scoping

**Date:** 2026-03-10  
**Status:** CLOSED  
**Tests:** 4341 passing (4297 → +44)

## Goal

Enforce role-based data visibility in existing API endpoints using the
`tenant_permissions` table and `get_permission_record()` helper from Phase 165.

## Files Changed

| File | Type | Summary |
|------|------|---------|
| `src/api/worker_router.py` | MODIFY | Worker auto-scoped to `permissions.worker_role`; admin/manager unrestricted; response gains `role_scoped` bool |
| `src/api/owner_statement_router.py` | MODIFY | Owner restricted to `permissions.property_ids`; others unrestricted; 403 on forbidden property |
| `src/api/financial_aggregation_router.py` | MODIFY | `_get_owner_property_filter()` + `_fetch_period_rows(property_ids)` → owner property scoping in all 4 endpoints |
| `tests/test_worker_role_scoping_contract.py` | NEW | 22 contract tests |
| `tests/test_owner_role_scoping_contract.py` | NEW | 22 contract tests |

## Design Decisions

**Worker scoping:** When `role='worker'`, the value at `permissions.worker_role`
overrides the caller-supplied `worker_role` query param. This prevents a worker
from requesting another role's tasks by spoofing the param.

**Owner scoping:** `permissions.property_ids` is an explicit allow-list. An empty
list blocks all properties. No `property_ids` key in permissions also blocks all
(secure-by-default). Admin and manager bypass all property restrictions.

**Best-effort pattern:** If the `tenant_permissions` lookup raises an exception,
the request falls through unrestricted. This keeps the endpoint always-up even
during permission DB degradation.

**Backward compat:** No permission record → no restriction. All pre-166 tests
continue passing without change since the lookup returns `None`.

## Validation

```
4341 passed, 2 failed (pre-existing SQLite invariants), 3 skipped
```

No regressions introduced.
