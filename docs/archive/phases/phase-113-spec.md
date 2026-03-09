# Phase 113 — Task Query API Specification

## Goal

Expose a task read and status-transition API on top of the task data built in
Phase 111 (`task_model.py`) and Phase 112 (`task_automator.py`). The router
reads from and writes to the `tasks` Supabase table. All endpoints are
JWT-authenticated and tenant-isolated.

## Endpoints

### `GET /tasks`

List tasks for the authenticated tenant.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| property_id | string | No | Filter by property |
| status | string | No | TaskStatus enum value |
| kind | string | No | TaskKind enum value |
| due_date | string | No | YYYY-MM-DD |
| limit | int | No | 1–100 (default 50) |

**Response 200:**
```json
{
  "tasks": [...],
  "count": 2
}
```

**Validation errors return 400 VALIDATION_ERROR.**

---

### `GET /tasks/{task_id}`

Return a single task by `task_id`.

- Cross-tenant reads return **404** (not 403) — avoids leaking existence.
- Returns `{"task": {...}}` on success.

---

### `PATCH /tasks/{task_id}/status`

Transition a task to a new status.

**Request body:**
```json
{
  "status": "ACKNOWLEDGED",
  "canceled_reason": "optional"
}
```

**Valid transitions (from task_model.py VALID_TASK_TRANSITIONS):**
```
PENDING       → ACKNOWLEDGED | CANCELED
ACKNOWLEDGED  → IN_PROGRESS | CANCELED
IN_PROGRESS   → COMPLETED | CANCELED
COMPLETED     → (terminal — no transitions)
CANCELED      → (terminal — no transitions)
```

**Error codes:**
- `VALIDATION_ERROR` (400) — missing/invalid status in body
- `NOT_FOUND` (404) — task not found for tenant
- `INVALID_TRANSITION` (422) — transition not allowed from current state
- `INTERNAL_ERROR` (500) — Supabase failure

**Response 200:** Full updated task object in `{"task": {...}}`.

---

## Invariants (Locked)

1. `task_router.py` never writes to `booking_state`, `event_log`, or `booking_financial_facts`.
2. `PATCH /status` writes ONLY to the `tasks` table.
3. Tenant isolation is always enforced with `.eq("tenant_id", tenant_id)`.
4. `VALID_TASK_TRANSITIONS` from `task_model.py` is the single source of truth — the router does not redefine transition rules.
5. All endpoints are read-only for GET; PATCH writes only the status and updated_at fields.

---

## New Error Codes (added to error_models.py)

| Code | HTTP Status | Use |
|------|-------------|-----|
| `NOT_FOUND` | 404 | Task not found for tenant |
| `INVALID_TRANSITION` | 422 | Status transition not allowed |

---

## Files Changed

| File | Change |
|------|--------|
| `src/tasks/task_router.py` | [NEW] — 3 endpoints |
| `src/api/error_models.py` | [MODIFY] — added NOT_FOUND, INVALID_TRANSITION |
| `src/main.py` | [MODIFY] — registered task_router |
| `tests/test_task_router_contract.py` | [NEW] — 50 contract tests |

---

## Tests

**50 contract tests across 16 groups (A–P):**

| Group | Area |
|-------|------|
| A | GET /tasks — success, empty list, count field |
| B | GET /tasks — all filter parameters |
| C | GET /tasks — validation (bad status, bad kind, bad limit) |
| D | GET /tasks — auth guard |
| E | GET /tasks — tenant isolation |
| F | GET /tasks/{id} — success, structure |
| G | GET /tasks/{id} — 404, cross-tenant isolation |
| H | GET /tasks/{id} — auth guard |
| I | PATCH /status — all valid transitions |
| J | PATCH /status — canceled_reason handling |
| K | PATCH /status — invalid transitions → 422 |
| L | PATCH /status — terminal state blocked |
| M | PATCH /status — body validation |
| N | PATCH /status — task not found |
| O | PATCH /status — auth guard |
| P | DB failure → 500 INTERNAL_ERROR (all 3 endpoints) |
