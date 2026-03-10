# Phase 165 — Permission Model Foundation

**Status:** Closed
**Prerequisite:** Phase 164 (Owner Statement UI)
**Date Closed:** 2026-03-10

## Goal

Establish the database schema and API layer for role-based access control in iHouse Core. The `tenant_permissions` table stores one row per user per tenant, with a role (`admin | manager | worker | owner`) and an arbitrary JSONB capability-flag map. The CRUD router lets admins manage permissions. The `get_jwt_scope()` helper enriches the JWT context (used by Phase 166+ for role-scoped endpoint enforcement). This phase is the foundation; enforcement happens in Phase 166.

## Invariant (if applicable)

- `tenant_permissions` UNIQUE(tenant_id, user_id) — one row per user per tenant.
- Valid roles: `admin | manager | worker | owner` — enforced by DB CHECK and application layer (400 on invalid).
- `get_permission_record()` and `get_jwt_scope()` are **best-effort and never raise** — missing record returns `None` / empty scope.
- POST /permissions is an **upsert** (on_conflict tenant_id, user_id) — safe to call repeatedly.

## Design / Files

| File | Change |
|------|--------|
| `migrations/phase_165_tenant_permissions.sql` | NEW — DDL: tenant_permissions table, UNIQUE, role CHECK, JSONB, RLS, updated_at trigger, 2 indexes. ⚠️ Not yet applied to Supabase. |
| `src/api/error_models.py` | MODIFIED — PERMISSION_NOT_FOUND + FORBIDDEN error codes + default messages |
| `src/api/permissions_router.py` | NEW — GET /permissions (list), GET /permissions/{user_id} (404 on miss), POST /permissions (upsert), DELETE /permissions/{user_id} (404 on miss). Role validation, JSONB field validation. get_permission_record() helper. |
| `src/api/auth.py` | MODIFIED — get_jwt_scope(db, tenant_id, user_id) → {role, permissions}. Best-effort. Lazy import. `from typing import Any` added. |
| `src/main.py` | MODIFIED — registered permissions_router |
| `tests/test_permissions_contract.py` | NEW — 29 contract tests: list/get/upsert/delete, role validation, 400/404/500, tenant isolation (dependency_overrides), get_permission_record(), get_jwt_scope() |

## Result

**4297 tests pass, 2 skipped** (pre-existing SQLite guard failures, unrelated).

⚠️ **Pending action:** Apply `migrations/phase_165_tenant_permissions.sql` to Supabase manually (MCP access was blocked this session).

⚠️ **Pending action:** `git push` — all work committed locally on branch `checkpoint/supabase-single-write-20260305-1747`. Push separately when GitHub connectivity is stable.
