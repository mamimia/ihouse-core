# Phase 1027 — Stale Task & Past-Task Hygiene

**Status:** Closed
**Prerequisite:** Phase 1026 — Operational Truth Semantics Lock
**Date Closed:** 2026-03-30

## Goal

Fixed confusion caused by old and historical tasks surfacing in worker and admin views. Implemented staleness filtering to prevent newly onboarded properties from surfacing historical operational tasks. Distinguished between real bugs and proof/synthetic tasks that polluted staging. Applied ZTEST prefix hygiene rule for all staging proof tasks.

## Invariant

- Historical tasks (prior to onboarding) must not surface as current operational tasks
- Proof tasks on staging must use ZTEST- prefix and be cleaned up after proof
- Staleness filter must apply to both admin and worker task surfaces

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | MODIFIED — staleness and date-range filtering added |
| `src/api/task_router.py` | MODIFIED — admin task list filters past-date tasks from default view |
| `scripts/cleanup_probe_tasks.sql` | NEW — removes ZTEST- prefixed probe tasks from staging |

## Result

Historical task bleed-through resolved. ZTEST hygiene rule established and enforced. KPG-500 (Emuna Villa) used as the primary live example for this cleanup.
