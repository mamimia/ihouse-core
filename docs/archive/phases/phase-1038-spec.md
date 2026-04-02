# Phase 1038 — Supervisory Role Assignment Hardening

**Status:** Closed
**Prerequisite:** Phase 1037 (Staff Onboarding Access Hardening)
**Date Closed:** 2026-04-02

## Goal

Fix the core OM assignment problem: `POST /staff/assignments` was incorrectly applying worker-lane validation to supervisory roles (manager, admin, owner), causing 400 errors and preventing OM assignment entirely. Fix the property row UI to show assigned supervisors instead of Primary/Backup badges for non-worker roles. Surface real backend errors in the UI instead of a generic "Save failed" message.

## Invariant (INV-1038-A)

- Supervisory roles (manager, admin, owner) bypass worker-lane validation on assignment POST.
- Supervisory assignments use `priority=100` (supervisor slot), not lane-based priority.
- Worker rows continue to use Primary/Backup Priority model — unchanged.
- `GET /staff/property-lane/{id}` returns a `supervisors[]` array alongside worker lane data.
- UI property rows branch on role: supervisory roles render supervisor chips; worker roles render Primary/Backup badges.

## Design / Files

| File | Change |
|------|--------|
| `src/api/permissions_router.py` | MODIFIED — `POST /staff/assignments`: fetch role + worker_roles together; manager/admin/owner bypass lane validation with priority=100; error message now includes sys_role and supervisory_roles hint |
| `src/api/permissions_router.py` | MODIFIED — `GET /staff/property-lane/{id}`: adds `supervisors[]` to response; separates manager/admin/owner from worker lanes; `perm_map` selects `role` column correctly |
| `ihouse-ui/app/(app)/admin/staff/[userId]/page.tsx` | MODIFIED — `apiFetch`: reads response body before throwing (surfaces real backend detail/message); `handleSave` catch: `setError(e.message)` instead of hardcoded string; lane data fetch changed from assigned-only to ALL properties (supervisor visibility); property rows: `isSupervisory` branch renders supervisor name chips (👤 Name) instead of Primary/Will-be-Primary badges |

## Result

Supervisory OM assignment E2E: POST returns 200, DB row created with priority=100, property row shows supervisor chips. Backend-proven. Orphaned `0330` tenant_permissions + staff_assignments rows cleaned (auth.users already gone from Phase 1037 cleanup).
