# Phase 888 — Staffing-to-Task Assignment Backfill

**Status:** Closed
**Prerequisite:** Phase 866 (Model B Concurrent Act As Sessions)
**Date Closed:** 2026-03-26

## Goal

Resolve operational inconsistency where future cleaning/operational tasks remained unassigned after staff-property assignment changes, due to a pure generation-time snapshot model. Implement a canonical backfill rule that keeps the future task board aligned with current staffing.

## Invariant

When staff-property assignments change, only future PENDING tasks are automatically adjusted. ACKNOWLEDGED, IN_PROGRESS, COMPLETED, and CANCELED tasks are NEVER auto-mutated — they represent active human commitments.

## Design / Files

| File | Change |
|------|--------|
| `src/api/permissions_router.py` | MODIFIED — added `_backfill_tasks_on_assign()`, `_clear_tasks_on_unassign()`, and `_ROLE_TO_TASK_ROLES` mapping |
| `src/api/manual_booking_router.py` | MODIFIED — added 422 guard blocking booking creation for non-approved properties |
| `ihouse-ui/app/(app)/admin/properties/[id]/page.tsx` | MODIFIED — hidden Add Booking button for non-approved properties |
| `ihouse-ui/app/(app)/admin/bookings/intake/page.tsx` | MODIFIED — property-scoped booking intake flow, filtered PropertySelect to approved-only |
| `docs/core/RULE_staffing_task_backfill.md` | NEW — canonical locked rule document |

## Result

**3-case staging proof:**
- Case A (assign new worker): 9/9 PENDING tasks backfilled
- Case B (remove, no replacement): 9/9 PENDING tasks cleared to UNASSIGNED
- Case C (replace A with B): 9/9 PENDING tasks moved to replacement worker

Pre-existing test failures (not introduced by this phase): ~20 failures across older contract test files.
