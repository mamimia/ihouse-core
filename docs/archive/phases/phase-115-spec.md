# Phase 115 — Task Writer

**Status:** Closed
**Prerequisite:** Phase 114 — Task Persistence Layer (`tasks` table DDL)
**Date Closed:** 2026-03-09

## Goal

Connect `task_automator.py` (Phase 112 — pure functions) to the `tasks` table (Phase 114) so that booking lifecycle events automatically create, cancel, and reschedule tasks in the database. Phase 115 closes the gap between the automation logic (pure, stateless) and the actual persistence layer.

## Invariant

- `task_writer.py` writes **only** to `tasks`. Never to `booking_state`, `event_log`, or `booking_financial_facts`.
- All writes are idempotent: upsert uses `on_conflict='task_id'` — DLQ replays do not create duplicate tasks.
- All public functions are **best-effort** — errors are logged and swallowed. The OTA ingestion pipeline is never blocked by a task write failure.
- Pattern matches `financial_writer.py` (Phase 66) and `ordering_trigger.py` (Phase 45).

## Design / Files

| File | Change |
|------|--------|
| `src/tasks/task_writer.py` | NEW — 3 entry points + serialization helper |
| `src/adapters/ota/service.py` | MODIFIED — wired task_writer for 3 event types |
| `tests/test_task_writer_contract.py` | NEW — 32 contract tests (Groups A–E) |

### task_writer.py Entry Points

| Function | Trigger | Writes |
|----------|---------|--------|
| `write_tasks_for_booking_created(...)` | BOOKING_CREATED → APPLIED | Upserts CHECKIN_PREP + CLEANING tasks |
| `cancel_tasks_for_booking_canceled(...)` | BOOKING_CANCELED → APPLIED | Sets PENDING tasks to CANCELED |
| `reschedule_tasks_for_booking_amended(...)` | BOOKING_AMENDED → APPLIED | Updates due_date on CHECKIN_PREP + CLEANING |

### service.py Changes

Three new best-effort blocks added to `ingest_provider_event_with_dlq`:

```python
# After BOOKING_CREATED APPLIED (Phase 115)
try:
    from tasks.task_writer import write_tasks_for_booking_created
    ...
except Exception:
    pass  # best-effort

# After BOOKING_AMENDED APPLIED (Phase 115)
try:
    from tasks.task_writer import reschedule_tasks_for_booking_amended
    ...
except Exception:
    pass  # best-effort

# After BOOKING_CANCELED APPLIED (Phase 115)
try:
    from tasks.task_writer import cancel_tasks_for_booking_canceled
    ...
except Exception:
    pass  # best-effort
```

### Test Groups

| Group | Coverage |
|-------|---------|
| A (10 tests) | `write_tasks_for_booking_created` — count, upsert, idempotency, field values |
| B (8 tests) | `cancel_tasks_for_booking_canceled` — cancel flow, no pending, error swallow |
| C (5 tests) | `reschedule_tasks_for_booking_amended` — reschedule, no-op when unchanged |
| D (5 tests) | `_task_to_row` — shape, enum serialization, field types |
| E (4 tests) | service.py wiring — called on APPLIED, not called on ALREADY_APPLIED, error doesn't block |

## Result

**32 new tests — all passing.**
**2662 total tests passing (32 new + 2630 pre-existing).**
2 pre-existing SQLite skips in `test_invariant_suite.py` — unrelated, unchanged.
