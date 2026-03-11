# Phase 232 — Guest Pre-Arrival Automation Chain

## Goal

Chain Phase 206 (pre-arrival tasks) and Phase 227 (guest messaging).
When a booking approaches check-in (1–3 days), the daily scanner auto-creates CHECKIN_PREP +
GUEST_WELCOME tasks and auto-drafts a check-in message. The draft is stored but never sent.

## Invariants

- **Idempotent:** One row per `(tenant_id, booking_id, check_in)` in `pre_arrival_queue`. Same booking scanned twice → skipped.
- **Best-effort per booking:** Exception on one booking never aborts the scan.
- **Never sends messages:** `draft_preview` is stored only.
- **Daily cron:** Runs at `IHOUSE_PRE_ARRIVAL_SCAN_HOUR` UTC (default 06:00).
- **No LLM dependency:** Heuristic draft only — scanner is fast and dependency-free.

## Files

### New
- `src/services/pre_arrival_scanner.py` — `run_pre_arrival_scan(db?)` — core scanner
- `src/api/pre_arrival_router.py` — `GET /admin/pre-arrival-queue`
- `supabase/migrations/20260311143000_phase232_pre_arrival_queue.sql` — `pre_arrival_queue` table
- `tests/test_pre_arrival_contract.py` — 22 contract tests
- `docs/archive/phases/phase-232-spec.md` — this file

### Modified
- `src/services/scheduler.py` — Job 4: `pre_arrival_scan` daily cron at 06:00 UTC
- `src/main.py` — `pre_arrival_router` registered (Phase 232)

## DB Schema: `pre_arrival_queue`

| Column | Type | Notes |
|--------|------|-------|
| id | BIGSERIAL PK | |
| tenant_id | TEXT | |
| booking_id | TEXT | |
| property_id | TEXT | nullable |
| check_in | DATE | |
| tasks_created | JSONB | list of task_ids |
| draft_written | BOOLEAN | |
| draft_preview | TEXT | max 500 chars |
| scanned_at | TIMESTAMPTZ | |

Unique constraint: `(tenant_id, booking_id, check_in)`

## Endpoint: GET /admin/pre-arrival-queue

Filters: `date` (check_in), `draft_written` (true/false), `limit` (1–100)
Ordered by `check_in ASC` (soonest arrivals first).
