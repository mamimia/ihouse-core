# Phase 1036 — OM-1: Stream Hardening

**Status:** Closed
**Prerequisite:** Phase 1035 (OM-1: Stream Redesign)
**Date Closed:** 2026-04-01

## Goal

Harden the OM Stream with canonical task ordering, ad-hoc task creation for managers, and improved booking scope clarity. Add a conflict guardrail in the UI when a manager tries to create a duplicate task.

## Invariant

- Ad-hoc task canonical ordering: CHECKOUT → CLEAN → CHECKIN within same property + same day.
- `POST /tasks/adhoc`: CHECKIN_PREP and CHECKOUT_VERIFY kinds are always blocked (auto-created only).
- Duplicate guardrail: 409 returned with `?force=true` override available.
- Lane-aware auto-assign: new ad-hoc tasks follow Primary/Backup assignment model.

## Design / Files

| File | Change |
|------|--------|
| `src/api/task_takeover_router.py` | NEW `POST /tasks/adhoc` — CLEANING/MAINTENANCE/GENERAL only; 409 duplicate + force override; lane-aware auto-assign; audit log |
| `ihouse-ui/app/(app)/manager/stream/page.tsx` | MODIFIED — canonical ordering (CHECKOUT→CLEAN→CHECKIN same property+day); `KindSequenceBadge`; Add Task button in header wired to `/tasks/adhoc`; conflict guardrail UI; scope-aware booking empty state |

## Result

Build clean. Deployed commit `054c83a`. Staging visual proof carried into Phase 1037/1038 session.
