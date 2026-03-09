# Phase 112 — Task Automation from Booking Events

**Status:** Closed
**Prerequisite:** Phase 111 (Task System Foundation)
**Date Closed:** 2026-03-09

## Goal

Implement the rule engine that automatically emits Tasks from booking lifecycle events. Pure Python functions — no database reads, no database writes.

## Invariant

- `task_automator.py` is **read-only and side-effect-free**.
- It never reads from `booking_state`, `event_log`, or any table.
- It never writes to any table.
- Task creation is deterministic (inherits `task_id` logic from Phase 111).
- Callers (task routers / schedulers) are responsible for persisting actions.

## Design / Files

| File | Change |
|------|--------|
| `src/tasks/task_automator.py` | NEW — three pure functions + action dataclasses |
| `tests/test_task_automator_contract.py` | NEW — 48 tests, Groups A–J |

## Automation Rules (Locked)

| Event | Action |
|-------|--------|
| `BOOKING_CREATED` | Emit **CHECKIN_PREP** (HIGH priority) + **CLEANING** (MEDIUM priority), both due on `check_in` date |
| `BOOKING_CANCELED` | Emit `TaskCancelAction` for each PENDING task of this booking |
| `BOOKING_AMENDED` | Emit `TaskRescheduleAction` for CHECKIN_PREP + CLEANING tasks if `check_in` date changed |

## Action Types

| Type | Fields |
|------|--------|
| `TaskCancelAction` | `task_id`, `booking_id`, `reason` — frozen dataclass |
| `TaskRescheduleAction` | `task_id`, `booking_id`, `kind`, `old_due_date`, `new_due_date` — frozen dataclass |

## BOOKING_AMENDED Filtering (locked)

- Only affects `CHECKIN_PREP` and `CLEANING` (due dates tied to check_in)
- Skips `MAINTENANCE`, `GENERAL`, `CHECKOUT_VERIFY`
- Skips terminal tasks (COMPLETED, CANCELED)
- Skips tasks where `due_date` already equals `new_check_in`
- Skips tasks for different `booking_id`

## Test Groups

| Group | What it tests |
|-------|---------------|
| A | BOOKING_CREATED: correct task types (CHECKIN_PREP first, CLEANING second), count=2 |
| B | BOOKING_CREATED: field values (tenant_id, booking_id, property_id, due_date=check_in, PENDING) |
| C | BOOKING_CREATED: deterministic task_ids, priorities, urgency labels, created_at default |
| D | BOOKING_CANCELED: emits one cancel action per pending task_id |
| E | BOOKING_CANCELED: empty list → no actions, custom reason, frozen |
| F | BOOKING_AMENDED: reschedules CHECKIN_PREP and CLEANING when date changes |
| G | BOOKING_AMENDED: no action if date unchanged or tasks list empty |
| H | BOOKING_AMENDED: skips COMPLETED and CANCELED; keeps IN_PROGRESS, ACKNOWLEDGED |
| I | BOOKING_AMENDED: only CHECKIN_PREP/CLEANING; filters MAINTENANCE/GENERAL/CHECKOUT_VERIFY |
| J | Pure-function invariants: no mutation of inputs, fresh objects per call |

## Result

**2580 tests pass, 2 pre-existing SQLite skips.**
Pure Python — no DB, no migrations, no external calls.
