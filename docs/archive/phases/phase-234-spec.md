# Phase 234 — Shift & Availability Scheduler

## Goal

Add worker availability tracking so managers can see who is available when,
and task routing can eventually prefer available workers.

## Invariants

- **No LLM dependency** — pure CRUD data layer
- **Upsert idempotency** — one row per `(tenant_id, worker_id, date)`
- **Tenant isolation** — all queries scoped to `tenant_id`
- **Worker self-service** — POST/GET `/worker/...` use JWT `user_id` claim
- **No writes to core tables** — only `worker_availability`

## Table: `worker_availability`

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | auto |
| tenant_id | text | indexed |
| worker_id | text | JWT user_id |
| date | date | |
| start_time | time | null = all-day |
| end_time | time | null = all-day |
| status | text | AVAILABLE \| UNAVAILABLE \| ON_LEAVE |
| notes | text | optional |
| UNIQUE | (tenant_id, worker_id, date) | idempotency |

## Endpoints

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| POST | /worker/availability | Worker | Set own availability for a date |
| GET | /worker/availability?from=&to= | Worker | View own slots (max 90 days) |
| GET | /admin/schedule/overview?date= | Manager | All workers grouped by status |

## Files

### New
- `supabase/migrations/20260311150000_phase234_worker_availability.sql`
- `src/api/worker_availability_router.py`
- `tests/test_worker_availability_contract.py`
- `docs/archive/phases/phase-234-spec.md` — this file

### Modified
- `src/main.py` — `worker_availability_router` registered (Phase 234)
