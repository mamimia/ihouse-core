# Phase 123 — Worker-Facing Task Surface

**Status:** Closed
**Prerequisite:** Phase 113 (Task Query API), Phase 117 (SLA Escalation Engine)
**Date Closed:** 2026-03-09

## Goal

Expose a role-scoped, worker-facing task surface on top of the existing `tasks` table.
Workers should be able to:

1. List their assigned tasks (filtered by `worker_role`, `status`, `date`)
2. Acknowledge a task (`PENDING → ACKNOWLEDGED`)
3. Mark a task as complete (`ACKNOWLEDGED | IN_PROGRESS → COMPLETED`)

This is a **dashboard-first** surface. Not mobile-first. No external channels yet.
The in-app task acknowledgement model is the source of truth.

## Invariants

- Reads/writes to `tasks` table only. NEVER touches `booking_state`, `event_log`,
  or `booking_financial_facts`.
- `worker_role` filter is enforced at DB level. Workers only see tasks for their role.
- Tenant isolation enforced at DB level (`.eq("tenant_id", tenant_id)`).
- Valid transitions only: acknowledge → PENDING→ACKNOWLEDGED, complete → *→COMPLETED.
- acknowledge uses VALID_TASK_TRANSITIONS from task_model.py.

## Design / Files

| File | Change |
|------|--------|
| `src/api/worker_router.py` | NEW — `/worker/tasks` GET, PATCH acknowledge, PATCH complete |
| `src/main.py` | MODIFIED — register worker_router |
| `tests/test_worker_router_contract.py` | NEW — contract tests Groups A–H, ~42 tests |
| `docs/archive/phases/phase-123-spec.md` | NEW (this file) |

## Endpoints

```
GET  /worker/tasks
     ?worker_role=CLEANER&status=PENDING&date=YYYY-MM-DD&limit=50

PATCH /worker/tasks/{task_id}/acknowledge
     Body: {} (no fields required)

PATCH /worker/tasks/{task_id}/complete
     Body: { "notes": "optional completion note" }
```

## Result

**~2995 tests pass, 2 pre-existing SQLite skips.**
No DB schema changes. Writes only to `tasks`. In-app only — no external channels.
