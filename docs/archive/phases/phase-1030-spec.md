# Phase 1030 — Task Lifecycle & Assignment Hardening

**Status:** Closed
**Prerequisite:** Phase 1029 — Default Worker Task Filter (COMPLETED Exclusion Hardened)
**Date Closed:** 2026-03-31

## Goal

Hardened all task lifecycle and assignment paths to enforce the Primary/Backup model end-to-end. Ensured that every task creation, rescheduling, and baton-transfer path resolves the correct Primary worker deterministically. Locked three new invariants covering task assignment healing across all creation paths.

## Invariant

- **INV-1010 (extended):** All CLEANING task creation paths (auto, early-checkout, amendment, ad-hoc) must resolve the Primary cleaner and assign if available. Silent `assigned_to = NULL` is a bug, not a valid state.
- **INV-1011 (extended):** Assignment healing is required in all task rescheduling paths (early-checkout ✅, amendment reschedule ✅).
- **INV-1012 (new):** Baton-transfer is lane-aware. Backup promotion must match the departing Primary's `worker_roles` lane. A checkout worker cannot inherit a cleaning task.

## Design / Files

| File | Change |
|------|--------|
| `src/tasks/task_writer.py` | MODIFIED — amendment reschedule healing: unassigned tasks inherit Priority 1 worker on date shift |
| `src/tasks/task_router.py` | MODIFIED — `POST /tasks/cleaning/adhoc` uses `ORDER BY priority ASC` — Primary always selected |
| `src/api/permissions_router.py` | MODIFIED — baton-transfer lane-aware: filters backup candidates by `worker_roles` overlap; promotion notice via direct JSONB write (dead RPC removed) |
| `src/api/worker_router.py` | MODIFIED — default status filter excludes COMPLETED + CANCELED (canonical backend enforcement) |
| `src/api/early_checkout_router.py` | MODIFIED — early-checkout rescheduling heals unassigned CLEANING tasks to current Primary |
| `tests/test_worker_router_contract.py` | MODIFIED — regression test A8: default GET /worker/tasks excludes COMPLETED and CANCELED |
| `scripts/cleanup_probe_tasks.sql` | NEW — staging hygiene: removes ZTEST- prefixed probe tasks |

## Result

**7,975 passed, 0 failed, 22 skipped.**

Staging-proven:
- ✅ Admin Pending view correctly excludes COMPLETED tasks (browser recording confirmed)
- ✅ DB audit: `priority` column populated on `staff_property_assignments` for all staging workers
- ✅ DB audit: KPG-502 correctly has Primary (priority=1) and Backup (priority=2) per lane

Deferred proofs (code correct, not live-flow proven):
- Live baton-transfer flow (remove Primary → verify Backup promoted and PENDING tasks moved)
- Worker promotion banner rendering on login
- POST /staff/assignments backfill on full live flow
- Amendment reschedule healing on live flow
- Ad-hoc cleaning Primary selection on live flow

Commit: `7732ab4`. Branch: `checkpoint/supabase-single-write-20260305-1747`.
