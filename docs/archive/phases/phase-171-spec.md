# Phase 171 — Admin Audit Log

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 28 contract tests  
**Total after phase:** 4448 passing

## Goal

Create an append-only compliance audit trail for every admin action (permission grants/revokes, provider registry changes, future admin mutations). Provides `write_audit_event()` as a shared utility and a queryable `GET /admin/audit-log` endpoint.

## Deliverables

### New Files
- `migrations/phase_171_admin_audit_log.sql` — `admin_audit_log` table: id UUID PK, tenant_id, actor_user_id TEXT, action TEXT, target_type TEXT, target_id TEXT, before_state JSONB, after_state JSONB, metadata JSONB, occurred_at TIMESTAMPTZ DEFAULT now(). 4 indexes (tenant+occurred_at, actor, target, action). RLS. DDL comment explicitly marking table as append-only.
- `tests/test_admin_audit_log_contract.py` — 28 contract tests

### Modified Files
- `src/api/admin_router.py` — `write_audit_event(db, *, tenant_id, actor_user_id, action, target_type, target_id, before_state, after_state, metadata)` helper added: append-only INSERT, best-effort, never raises. `GET /admin/audit-log` endpoint: filterable by action / actor_user_id / target_type / target_id, limit 1–500 (default 100), tenant-scoped, ordered occurred_at DESC.

## Key Design Decisions
- `write_audit_event()` is best-effort: failure to write audit log never blocks the operation being audited
- No UPDATE or DELETE permitted on `admin_audit_log` — DDL comment + RLS enforce this
- `before_state` / `after_state` as JSONB allow structured diff recording for any entity type
- action strings are free-form TEXT (`'permission.granted'`, `'provider.patched'`) — not an enum, extensible

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Audit log is append-only — no mutation of existing audit records ever permitted ✅
