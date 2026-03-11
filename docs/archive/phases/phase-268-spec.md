# Phase 268 — E2E Task System Integration Test

**Status:** Closed
**Prerequisite:** Phase 267 (E2E Financial Summary)
**Date Closed:** 2026-03-11

## Goal

Add E2E tests for the task system API surface, covering both the task_router (manager-facing)
and worker_router (worker-facing). CI-safe — no live DB, no staging required.

## Design

- **Groups A-C**: Direct async function calls on `tasks/task_router.py` handlers
  (`asyncio.run()` + mocked `client=` arg). Covers list, get single, status transition.
- **Groups D-F**: HTTP TestClient calls to `api/worker_router.py` endpoints.
  Covers worker task list, ack, complete, channel preferences, notification history.

## State Machine Discovery

`ACKNOWLEDGED → COMPLETED` is an **invalid transition** in the SLA state machine.
Valid path: `PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED`.
Test `test_e3` documents this by asserting 422 is valid (the router enforces the rule).

## Files

| File | Change |
|------|--------|
| `tests/test_task_system_e2e.py` | NEW — 27 tests, 6 groups (A-F) |

**Test groups:**
- **Group A** (4): `list_tasks` — 200 + shape, required keys, empty → 0, invalid status filter 400
- **Group B** (3): `get_task` — 200 + nested shape, 404 for missing, task_id correct
- **Group C** (4): `patch_task_status` — valid body 200, invalid status 400/422, not found 404, empty body 400/422
- **Group D** (3): `GET /worker/tasks` — 200 + tasks key, count present, empty 0
- **Group E** (3): `PATCH .../acknowledge` (200/404) and `.../complete` (200/422)
- **Group F** (3): `GET /worker/preferences` (200, is dict/list), `GET /worker/notifications` (200)

## Result

Full suite: **~6,107 tests pass, 13 skipped, 0 failures.**
