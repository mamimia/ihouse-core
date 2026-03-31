# Phase 1029 — Default Worker Task Filter (COMPLETED Exclusion Hardened)

**Status:** Closed
**Prerequisite:** Phase 1028 — Primary/Backup Model Decision & Baton-Transfer Architecture
**Date Closed:** 2026-03-30

## Goal

Hardened the default task filter for the worker task surface. Previously the default filter only excluded CANCELED tasks — COMPLETED tasks were leaking through into the default Pending view. This fix moved the COMPLETED exclusion into the canonical backend, not just a UI filter. Added regression test to prevent future regressions.

## Invariant

- `GET /worker/tasks` default response must never include COMPLETED or CANCELED tasks
- Terminal task states (COMPLETED, CANCELED) must be excluded at the API layer, not only at the UI layer

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | MODIFIED — default status filter explicitly excludes both COMPLETED and CANCELED |
| `tests/test_worker_router_contract.py` | MODIFIED — regression test A8 added: default GET /worker/tasks excludes COMPLETED and CANCELED |

## Result

7,975 passed, 0 failed (pre-existing), 22 skipped. Canonical backend exclusion of terminal states in worker task default filter. Regression test A8 locks this permanently.
