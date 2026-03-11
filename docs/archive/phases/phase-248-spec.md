# Phase 248 — Maintenance & Housekeeping Task Templates

**Status:** Closed
**Prerequisite:** Phase 247 (Guest Feedback Collection API)
**Date Closed:** 2026-03-11

## Goal

Allow operators to define reusable task blueprints (templates) for recurring
maintenance and housekeeping work. Templates can be linked to booking events
for auto-spawning and carry priority, effort estimates, and worker instructions.

## New Table

**`task_templates`** (migration: `20260311165500_phase248_task_templates.sql`)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | auto-generated |
| tenant_id | TEXT | RLS scoped |
| title | TEXT | UNIQUE per tenant |
| kind | TEXT | housekeeping / maintenance / inspection |
| priority | TEXT | critical / high / normal / low (CHECK) |
| estimated_minutes | INTEGER | > 0 if set |
| trigger_event | TEXT | optional auto-spawn hook |
| instructions | TEXT | worker-facing steps |
| active | BOOLEAN | soft-delete flag |
| created_at / updated_at | TIMESTAMPTZ | auto-managed |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/task-templates` | List with kind/trigger/active filters |
| `POST` | `/admin/task-templates` | Create or upsert template |
| `DELETE` | `/admin/task-templates/{id}` | Soft-delete (active=False) |

## Files

| File | Change |
|------|--------|
| `supabase/migrations/20260311165500_phase248_task_templates.sql` | NEW |
| `src/api/task_template_router.py` | NEW |
| `src/main.py` | MODIFIED |
| `tests/test_task_template_contract.py` | NEW — 26 tests (8 groups) |

## Result

**~5,790 tests pass. 0 failures. Exit 0.**
