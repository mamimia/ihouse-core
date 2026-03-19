# Phase 846 — Worker Role Scoping & Dynamic Task Filtering

**Status:** Closed
**Prerequisite:** Phase 845
**Date Closed:** 2026-03-19

## Goal

Modernize the backend `/worker/tasks` endpoint to support plural JSONB properties for assigned `worker_roles`, replacing the singular string array field `worker_role` and solving scoping isolation bugs where workers could see tasks not assigned to their exact capabilities. Admin views are preserved.

## Invariant (if applicable)

If an unprivileged user has an empty or missing `worker_roles` capacity array, they must natively be isolated and see 0 items. They must never fall back to seeing 'All tasks'.

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | MODIFIED — refactored `.in_("worker_role", list(effective_worker_roles))` and ensured a dummy block `__NO_ROLES_ASSIGNED__` falls back securely for workers with zero roles over `is_worker=True`. Fixed a logical `NameError`. |

## Result

**N tests pass, M skipped.** Roles enforce absolute isolation strictly within the worker router endpoint, returning only relevant kinds (`CHECKIN`, `CLEANER` etc).
