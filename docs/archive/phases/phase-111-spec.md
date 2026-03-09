# Phase 111 — Task System Foundation

**Status:** Closed
**Prerequisite:** Phase 110 (OTA Reconciliation Implementation)
**Date Closed:** 2026-03-09

## Goal

Define the core data model for the iHouse Core task system. Build all enums, mapping tables, and the `Task` dataclass required by Phase 112 (task automator) and Phase 113 (task query API).

## Invariant

- `task_model.py` is a **pure data model** — no DB reads/writes, no external API calls.
- CRITICAL ACK SLA = **5 minutes**. This value is locked per the escalation engine spec (Phase 91). Do not change.
- Task `task_id` is deterministic: `sha256(kind:booking_id:property_id)[:16]`.
- Task system never writes to `event_log` or `booking_state`.

## Design / Files

| File | Change |
|------|--------|
| `src/tasks/__init__.py` | NEW — empty package marker |
| `src/tasks/task_model.py` | NEW — all enums, mapping tables, Task dataclass |
| `tests/test_task_model_contract.py` | NEW — 68 tests, Groups A–I |

## Enums

| Enum | Values |
|------|--------|
| `TaskKind` | CLEANING, CHECKIN_PREP, CHECKOUT_VERIFY, MAINTENANCE, GENERAL |
| `TaskStatus` | PENDING, ACKNOWLEDGED, IN_PROGRESS, COMPLETED, CANCELED |
| `TaskPriority` | LOW, MEDIUM, HIGH, CRITICAL |
| `WorkerRole` | CLEANER, PROPERTY_MANAGER, MAINTENANCE_TECH, INSPECTOR, GENERAL_STAFF |

All enums inherit from `str` for clean JSON serialization.

## Mapping Tables (all locked)

| Table | Purpose |
|-------|---------|
| `PRIORITY_URGENCY` | Priority → display label ("normal"/"urgent"/"critical") |
| `PRIORITY_ACK_SLA_MINUTES` | Priority → ACK SLA in minutes (CRITICAL = 5, locked) |
| `KIND_DEFAULT_WORKER_ROLE` | TaskKind → default WorkerRole |
| `KIND_DEFAULT_PRIORITY` | TaskKind → default TaskPriority |
| `VALID_TASK_TRANSITIONS` | TaskStatus → frozenset of allowed next statuses |
| `TERMINAL_STATUSES` | {COMPLETED, CANCELED} — no further transitions |

## Valid State Transitions

```
PENDING → ACKNOWLEDGED → IN_PROGRESS → COMPLETED
PENDING → CANCELED
ACKNOWLEDGED → CANCELED
IN_PROGRESS → CANCELED
COMPLETED → (none)
CANCELED → (none)
```

## Task.build() Factory

Auto-derives: `task_id`, `priority` (from kind default), `worker_role` (from kind default), `urgency` (from priority), `ack_sla_minutes` (from priority). Initial `status` always `PENDING`.

## Test Groups

| Group | What it tests |
|-------|---------------|
| A | Enum completeness (4 enums, all values, str subclass) |
| B | Mapping tables (all priorities/kinds covered, valid labels, positive ints) |
| C | Task.build() factory (18 tests: defaults, overrides, field derivation) |
| D | task_id determinism (same/different inputs, length=16) |
| E | Lifecycle helpers (is_terminal, can_transition_to, allowed_next_statuses) |
| F | with_status() (new object, fields preserved, canceled_reason) |
| G | CRITICAL ACK SLA = 5 minutes (invariant — 3 tests) |
| H | Urgency label derivation (4 priorities → correct labels) |
| I | Terminal status invariants (no transitions, reachability) |

## Result

**2532 tests pass, 2 pre-existing SQLite skips.**
Pure Python model — no DB, no migrations, no external calls.
