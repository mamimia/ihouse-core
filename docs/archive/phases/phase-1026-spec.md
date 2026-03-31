# Phase 1026 — Operational Truth Semantics Lock

**Status:** Closed
**Prerequisite:** Phase 1025 — Public Property Submission Flow Hardening
**Date Closed:** 2026-03-30

## Goal

Locked canonical Operational Truth semantics that define how task states map to operational surfaces. Resolved confusion between ACKNOWLEDGED and IN_PROGRESS in admin views. Established the canonical rules for Pending, In Progress, and Done buckets across admin, worker, and preview surfaces.

## Invariant

- PENDING = all incomplete tasks (includes ACKNOWLEDGED and IN_PROGRESS — not done yet)
- ACKNOWLEDGED = "I saw this task and intend to handle it" — does NOT mean work started
- IN_PROGRESS = actual live started work
- Done = COMPLETED and CANCELED only
- COMPLETED and CANCELED must never appear in the Pending default view

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | MODIFIED — default filter corrected to exclude COMPLETED + CANCELED |
| `ihouse-ui/app/(app)/admin/tasks/` | MODIFIED — admin pending view excludes terminal states |
| Documentation | Operational Truth semantics locked in this phase |

## Result

Canonical task-state semantics locked. Admin pending view corrected. Worker task default view corrected. These rules apply to all surfaces from this phase forward.
