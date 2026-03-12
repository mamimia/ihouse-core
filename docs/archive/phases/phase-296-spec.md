# Phase 296 — Multi-Tenant Organization Foundation

**Status:** Closed
**Prerequisite:** Phase 295 (Documentation Truth Sync XV)
**Date Closed:** 2026-03-12

## Goal

Introduce the organization layer above individual tenant_ids. Enables multiple users/tenants to operate under a shared org umbrella — prerequisite for owner portal, multi-user management, and role-based access at the org level.

## Design Decisions

- `tenant_id` (JWT `sub`) is NEVER replaced or modified. Org layer is purely additive.
- A tenant_id belongs to at most one org (enforced by UNIQUE constraint in `tenant_org_map`).
- `tenant_org_map` is kept in sync with `org_members` via the `sync_tenant_org_map` DB trigger (no application-layer sync needed).
- All existing booking/financial/task endpoints are **unaffected** — they continue using tenant_id directly.
- Org roles: `org_admin` | `manager` | `member`. Creator auto-enrolled as `org_admin`.
- Last-admin guard: `DELETE /admin/org/{org_id}/members/{tid}` returns 422 if caller is the sole org_admin.

## Files Changed

| File | Change |
|------|--------|
| `artifacts/supabase/migrations/phase-296-organizations.sql` | NEW — organizations + org_members + tenant_org_map + trigger |
| `src/services/organization.py` | NEW — 7 pure service functions |
| `src/api/org_router.py` | NEW — 6 API endpoints |
| `tests/test_org_contract.py` | NEW — 37 contract tests (service + router) |
| `src/main.py` | MODIFIED — org_router registered (line 237) |

## API Surface

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /admin/org | JWT | Create org (caller becomes org_admin) |
| GET | /admin/org | JWT | List caller's orgs |
| GET | /admin/org/{org_id} | JWT + member | Get org details |
| GET | /admin/org/{org_id}/members | JWT + member | List members |
| POST | /admin/org/{org_id}/members | JWT + org_admin | Add member |
| DELETE | /admin/org/{org_id}/members/{tid} | JWT + org_admin | Remove member |

## Result

**37 new tests pass (37/37). All existing tests unaffected. Total: 6,253+ tests. Exit 0.**
