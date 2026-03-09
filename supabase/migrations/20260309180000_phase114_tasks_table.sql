-- Phase 114 — Task Persistence Layer
-- Creates the `tasks` table with RLS and performance indexes.
--
-- This table is the persistence backend for:
--   task_router.py  (Phase 113) — GET /tasks, GET /tasks/{id}, PATCH /tasks/{id}/status
--   task_automator.py (Phase 112) — pure task creation (output persisted in Phase 115)
--
-- Invariant: PATCH /status writes ONLY to this table. Never to booking_state,
-- event_log, or booking_financial_facts.


-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.tasks (
    task_id         TEXT        PRIMARY KEY,
    tenant_id       TEXT        NOT NULL,
    kind            TEXT        NOT NULL,   -- TaskKind enum value
    status          TEXT        NOT NULL,   -- TaskStatus enum value
    priority        TEXT        NOT NULL,   -- TaskPriority enum value
    urgency         TEXT        NOT NULL,   -- "normal" | "urgent" | "critical"
    worker_role     TEXT        NOT NULL,   -- WorkerRole enum value
    ack_sla_minutes INTEGER     NOT NULL,
    booking_id      TEXT        NOT NULL,
    property_id     TEXT        NOT NULL,
    due_date        DATE        NOT NULL,
    title           TEXT        NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes           JSONB       NOT NULL DEFAULT '[]'::jsonb,
    canceled_reason TEXT
);


-- ---------------------------------------------------------------------------
-- Row-Level Security
-- Matches pattern from booking_state and booking_financial_facts:
--   - service_role bypasses RLS (used by ingest pipeline)
--   - anon/authenticated can only touch their own tenant rows
-- ---------------------------------------------------------------------------

ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

-- Service role: full access (used by task_router via service role key)
CREATE POLICY "tasks_service_role_all"
    ON public.tasks
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users: tenant-isolated reads only
CREATE POLICY "tasks_tenant_read"
    ON public.tasks
    FOR SELECT
    TO authenticated
    USING (tenant_id = current_setting('request.jwt.claims', true)::jsonb->>'sub');

-- Authenticated users: tenant-isolated updates only (status transitions via API)
CREATE POLICY "tasks_tenant_update"
    ON public.tasks
    FOR UPDATE
    TO authenticated
    USING (tenant_id = current_setting('request.jwt.claims', true)::jsonb->>'sub')
    WITH CHECK (tenant_id = current_setting('request.jwt.claims', true)::jsonb->>'sub');


-- ---------------------------------------------------------------------------
-- Indexes
-- Three composite indexes covering the primary query patterns in task_router.py
-- ---------------------------------------------------------------------------

-- GET /tasks?status=... (most common filter — worker task list by status)
CREATE INDEX IF NOT EXISTS ix_tasks_tenant_status
    ON public.tasks (tenant_id, status);

-- GET /tasks?property_id=... (operations dashboard — tasks by property)
CREATE INDEX IF NOT EXISTS ix_tasks_tenant_property
    ON public.tasks (tenant_id, property_id);

-- GET /tasks?due_date=... (operations board — tasks due today)
CREATE INDEX IF NOT EXISTS ix_tasks_tenant_due_date
    ON public.tasks (tenant_id, due_date);


-- ---------------------------------------------------------------------------
-- Comments (for Supabase Studio clarity)
-- ---------------------------------------------------------------------------

COMMENT ON TABLE public.tasks IS
    'Operational task items generated from booking events. '
    'Written by task_writer (Phase 115). '
    'Read and transitioned by task_router (Phase 113). '
    'task_id is deterministic: sha256(kind:booking_id:property_id)[:16].';

COMMENT ON COLUMN public.tasks.task_id IS
    'Deterministic 16-char hex: sha256(kind:booking_id:property_id)[:16]. '
    'Acts as natural deduplication key.';

COMMENT ON COLUMN public.tasks.ack_sla_minutes IS
    'Acknowledgement SLA in minutes. CRITICAL tasks have a fixed 5-minute SLA (locked).';

COMMENT ON COLUMN public.tasks.notes IS
    'Append-only JSON array of operator or worker notes. Default empty array.';
