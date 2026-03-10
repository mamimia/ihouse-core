# Phase 167 — Permissions Routing

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** ~20 contract tests  
**Total after phase:** ~4330 passing

## Goal

Create the permissions API layer: grant and revoke named capabilities per user, and list a user's current permissions. Required by the Admin Settings UI (Phase 169) and role-based scoping enforcement (Phase 166).

## Deliverables

### New Files
- `src/api/permissions_router.py` — `PATCH /permissions/{user_id}/grant` (body: capability TEXT), `PATCH /permissions/{user_id}/revoke` (body: capability TEXT), `GET /permissions/{user_id}` (list capabilities for user, tenant-scoped). 404 if user_id not found in permission store.

### Modified Files
- `src/main.py` — permissions_router registered
- `src/api/permissions_router.py` [Phase 173 backfill] — `write_audit_event()` wired into grant and revoke endpoints

### New Test Files
- `tests/test_permissions_router_contract.py` — ~20 contract tests

## Key Design Decisions
- Capabilities are TEXT strings (e.g. `'financial:read'`, `'admin:settings'`) — not an enum, extensible without migration
- Grant is idempotent (if already granted, no error)
- Revoke is idempotent (if not granted, no error)
- Permissions stored in `user_permissions` table (created alongside this phase)
- Audit events written for grant/revoke (Phase 173 closed this debt)

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Permissions are a side-table — zero canonical state impact ✅
