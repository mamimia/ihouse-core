# Phase 345 — Multi-Tenant Flow E2E Integration Tests

**Closed:** 2026-03-12
**Category:** 🔐 Multi-Tenant / Testing / E2E
**Test file:** `tests/test_multi_tenant_e2e.py`

## Summary

First-ever end-to-end integration tests verifying the multi-tenant organization
lifecycle, membership management, tenant data isolation, cross-tenant access guards,
and JWT authentication boundary through the HTTP API layer.

## Tests Added: 36

### Group A — Org Lifecycle (8 tests)
- Create org (201), enrollment verification, list orgs, get org details
- Custom slug, duplicate slug, 404 for nonexistent org

### Group B — Membership CRUD (5 tests)
- Add member (201), list members, remove member, last-admin guard (422), duplicate member

### Group C — Tenant Data Isolation (5 tests)
- Bookings scoped to tenant, single booking tenant enforcement
- Tasks scoped to tenant, financial summary scoped to tenant, properties scoped to tenant

### Group D — Cross-Tenant Guards (4 tests)
- Non-member cannot access org details (403)
- Non-admin cannot add/remove members (403)
- Non-member cannot list members (403)

### Group E — Auth Boundary (6 tests)
- Dev-mode returns "dev-tenant", explicit opt-in check
- JWT sub claim → tenant_id, missing sub → 403, expired → 403, wrong secret → 403

### Group F — Service Invariants (5 tests)
- Deterministic slug generation, special char cleaning
- Valid roles enforcement, empty name rejection
- tenant_org_map read-path verification

### Group G — Full Lifecycle Flow (3 tests)
- Create → list shows org
- Add member → list shows both
- Remove member → list shows one

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 6,777 | 6,813 |
| Test files | 228 | 229 |
| New tests | — | 36 |

## Key Files

- `tests/test_multi_tenant_e2e.py` — NEW (36 tests)
- `src/api/org_router.py` — tested (6 endpoints)
- `src/services/organization.py` — tested (7 functions)
- `src/api/auth.py` — tested (JWT verification boundary)
