# Phase 114 — Task Persistence Layer: Supabase `tasks` Table DDL

**Status:** Closed
**Prerequisite:** Phase 113 — Task Query API
**Date Closed:** 2026-03-09

## Goal

Create the Supabase `tasks` table so that `task_router.py` (Phase 113) has a real persistence backend. Phase 113 implemented the full task query and transition API, but the table it reads from and writes to did not yet exist in Supabase. Phase 114 creates it with all required columns, tenant-isolation RLS policies, and the three performance indexes needed by the query patterns in `task_router.py`.

## Invariant

- `PATCH /tasks/{task_id}/status` writes **only** to `tasks`. Never to `booking_state`, `event_log`, or `booking_financial_facts`.
- `task_id` is deterministic: `sha256(kind:booking_id:property_id)[:16]`. The schema enforces this via TEXT PRIMARY KEY (no sequence, no auto-generated ID).
- RLS pattern matches `booking_state` and `booking_financial_facts`: service_role bypasses RLS; authenticated users are tenant-isolated via `request.jwt.claims`.

## Design / Files

| File | Change |
|------|--------|
| `supabase/migrations/20260309180000_phase114_tasks_table.sql` | NEW — `CREATE TABLE tasks`, 3 RLS policies, 3 composite indexes, column comments |

### Schema (18 columns)

| Column | Type | Notes |
|--------|------|-------|
| `task_id` | TEXT PRIMARY KEY | Deterministic sha256[:16] |
| `tenant_id` | TEXT NOT NULL | RLS pivot field |
| `kind` | TEXT NOT NULL | TaskKind enum value |
| `status` | TEXT NOT NULL | TaskStatus enum value |
| `priority` | TEXT NOT NULL | TaskPriority enum value |
| `urgency` | TEXT NOT NULL | "normal" / "urgent" / "critical" |
| `worker_role` | TEXT NOT NULL | WorkerRole enum value |
| `ack_sla_minutes` | INTEGER NOT NULL | CRITICAL = 5 min (locked) |
| `booking_id` | TEXT NOT NULL | Canonical booking_id |
| `property_id` | TEXT NOT NULL | |
| `due_date` | DATE NOT NULL | |
| `title` | TEXT NOT NULL | |
| `description` | TEXT | Nullable |
| `created_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `updated_at` | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| `notes` | JSONB NOT NULL DEFAULT '[]' | Append-only in spirit |
| `canceled_reason` | TEXT | Nullable |

### RLS Policies

| Policy | Role | Operation |
|--------|------|-----------|
| `tasks_service_role_all` | service_role | ALL (bypass) |
| `tasks_tenant_read` | authenticated | SELECT, tenant-isolated |
| `tasks_tenant_update` | authenticated | UPDATE, tenant-isolated |

### Indexes

| Index | Columns | Purpose |
|-------|---------|---------|
| `ix_tasks_tenant_status` | (tenant_id, status) | GET /tasks?status= |
| `ix_tasks_tenant_property` | (tenant_id, property_id) | GET /tasks?property_id= |
| `ix_tasks_tenant_due_date` | (tenant_id, due_date) | GET /tasks?due_date= |

## Result

**Migration applied and verified via `supabase db push`.**
Live E2E test confirmed: INSERT, SELECT, UPDATE, DELETE all function correctly via service role key.
No Python source files changed. No test count change — table infrastructure only.
2630 tests still passing (no regression).
