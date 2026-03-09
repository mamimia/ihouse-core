# iHouse Core — Handoff to New Chat
## Phase 113 Complete → Phase 114 Begins

**Date:** 2026-03-09
**Reason for handoff:** Chat context at ~90%, initiating clean handoff per BOOT.md protocol.

---

## State Summary

| Field | Value |
|-------|-------|
| Last Closed Phase | **Phase 113 — Task Query API** |
| Current Phase | **Phase 114** (not yet started) |
| Total Tests Passing | **2630** (2 pre-existing SQLite skips) |
| Branch | `checkpoint/supabase-single-write-20260305-1747` |

---

## What Was Completed in This Chat Session

| Phase | Title | Tests Added | Total |
|-------|-------|-------------|-------|
| 109 | Booking Date Range Search | +36 | 2437 |
| 110 | OTA Reconciliation Implementation | +27 | 2464 |
| 111 | Task System Foundation | +68 | 2532 |
| 112 | Task Automation from Booking Events | +48 | 2580 |
| 113 | Task Query API | +50 | 2630 |

**Also created this session (non-phase work):**
- `docs/core/planning/ui-architecture.md` — UI/product architecture forward planning note (7AM rule, role model, 6 surfaces)
- `docs/core/planning/ui-architecture-enhanced.md` — Full enhanced UI vision (market gap analysis, wireframes, worker issue flow, permission manifest model, feature comparison table)
- `releases/iHouseCore-v2-Phase112.zip` — Full project ZIP at Phase 112

---

## Last Closed Phase — Phase 113 Detail

**Files created/modified:**
- `src/tasks/task_router.py` — [NEW] 3 endpoints
- `src/api/error_models.py` — [MODIFY] `ErrorCode.NOT_FOUND`, `ErrorCode.INVALID_TRANSITION`
- `src/main.py` — [MODIFY] `task_router` registered
- `tests/test_task_router_contract.py` — [NEW] 50 tests, Groups A–P
- `docs/archive/phases/phase-113-spec.md` — [NEW]

**Endpoints:**
```
GET  /tasks                     filters: property_id, status, kind, due_date, limit(1-100)
GET  /tasks/{task_id}           404 tenant-isolated (cross-tenant → 404 not 403)
PATCH /tasks/{task_id}/status   VALID_TASK_TRANSITIONS enforced, 422 INVALID_TRANSITION
```

**Invariant:** `PATCH /status` writes only to `tasks` table. Never touches `booking_state`, `event_log`, or `booking_financial_facts`.

---

## Phase 114 — Next Objective

**Phase 114: Task Persistence Layer — Supabase `tasks` Table DDL**

The task_router (Phase 113) reads/writes the `tasks` table — but that table does not yet exist in Supabase. Phase 114 creates it.

**What needs to happen:**
1. Write a Supabase migration: `CREATE TABLE tasks (...)` with all required columns
2. Add RLS policy: tenant isolation via `tenant_id`
3. Add indexes: `(tenant_id, status)`, `(tenant_id, property_id)`, `(tenant_id, due_date)`
4. Verify migration applies cleanly
5. Contract test that the router works against the real Supabase schema

**Required columns** (from `task_model.py` + `task_router.py`):
```sql
task_id          TEXT PRIMARY KEY
tenant_id        TEXT NOT NULL
kind             TEXT NOT NULL   -- TaskKind enum value
status           TEXT NOT NULL   -- TaskStatus enum value
priority         TEXT NOT NULL   -- TaskPriority enum value
urgency          TEXT NOT NULL
worker_role      TEXT NOT NULL
ack_sla_minutes  INTEGER NOT NULL
booking_id       TEXT NOT NULL
property_id      TEXT NOT NULL
due_date         DATE NOT NULL
title            TEXT NOT NULL
description      TEXT
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
notes            JSONB DEFAULT '[]'
canceled_reason  TEXT
```

**RLS:** Row-Level Security must match pattern from `booking_state` and `booking_financial_facts`.

---

## Key Files the Next Agent Must Read First

Per BOOT.md order:
1. `docs/core/BOOT.md` ← start here
2. `docs/core/governance.md`
3. `docs/core/current-snapshot.md`
4. `docs/core/work-context.md`
5. `docs/core/live-system.md`
6. `docs/core/phase-timeline.md` (last section only — Phase 113 at end)
7. `docs/core/construction-log.md` (last section only — Phase 113 at end)

---

## Task System File Map

```
src/tasks/
  __init__.py          ← package marker
  task_model.py        ← Phase 111: enums, mappings, Task dataclass, VALID_TASK_TRANSITIONS
  task_automator.py    ← Phase 112: tasks_for_booking_created, actions_for_booking_canceled, actions_for_booking_amended
  task_router.py       ← Phase 113: GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status

tests/
  test_task_model_contract.py     ← 68 tests
  test_task_automator_contract.py ← 48 tests
  test_task_router_contract.py    ← 50 tests
```

---

## Locked Invariants the Next Agent Must Respect

| Invariant | Source |
|-----------|--------|
| CRITICAL ACK SLA = 5 min | `task_model.py` PRIORITY_ACK_SLA_MINUTES |
| task_id is deterministic | `Task.build()` |
| task_automator.py is pure (no DB) | Phase 112 design |
| task_router.py PATCH writes ONLY to `tasks` table | Phase 113 invariant |
| booking_state is append-only via event_log/apply_envelope | Phase 20+ canonical invariant |
| Financial data lives only in booking_financial_facts | Phase 65+ invariant |

---

## Context on Roadmap (Phases 114–130)

From `docs/core/planning/ui-architecture-enhanced.md` and `docs/core/roadmap.md`:

| Phase | Area |
|-------|------|
| **114** | Tasks DB — Supabase `tasks` table migration + RLS |
| **115** | Task Writer — persist `task_automator` output to DB after booking events |
| **116** | Financial Aggregation API — `GET /financial/summary`, by-property revenue |
| **117** | Property Readiness View API — aggregate task + booking state per property |
| **118** | Worker Communication Channel — LINE/WhatsApp/Telegram integration (channel dispatcher) |
| **119** | Notification Dispatch — send task notifications to workers via channel |
| **120** | Operations Dashboard API — aggregated today view (arrivals, departures, tasks, readiness) |
| **121–122** | Operations Dashboard UI — web frontend (Next.js) |
| **123–125** | Manager Web App — bookings, tasks, financial, property views |
| **126–128** | Admin Web App — settings, integrations, permissions, escalation |
| **129–130** | Owner Portal — statement, revenue, payout |

---

## Tech Stack Quick Reference

| Layer | Tech |
|-------|------|
| API | FastAPI + uvicorn |
| Auth | JWT (IHOUSE_JWT_SECRET) — dev env returns 'dev-tenant' if unset |
| DB | Supabase (PostgreSQL + RLS) |
| Tests | pytest with MagicMock + TestClient |
| Python path | `PYTHONPATH=src python -m pytest` |
| Git branch | `checkpoint/supabase-single-write-20260305-1747` |

---

## Known Pre-Existing Issues (Do Not Fix Unless Explicitly Requested)

- 2 SQLite failures in `tests/invariants/test_invariant_suite.py` — `test_booking_overlaps_are_tracked` and `test_booking_conflict_consistency`. Pre-existing, unrelated to task system.
- Pyre2 linter false positives throughout (cannot find imports) — all pass under pytest.

---

*Handoff prepared 2026-03-09 by closing AI. Next agent: read BOOT.md first, then proceed to Phase 114.*
