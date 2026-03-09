-- Phase 144 — Outbound Sync Result Persistence
-- Stores every ExecutionResult as an append-only audit log row.
-- Writers: outbound_executor.py (via sync_log_writer.py) after each sync.
-- Readers: Phase 145 Outbound Sync Log Inspector.
--
-- Apply in Supabase SQL editor (idempotent — safe to run multiple times).

-- -----------------------------------------------------------------------
-- Table
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS outbound_sync_log (
    id          BIGSERIAL       PRIMARY KEY,
    booking_id  TEXT            NOT NULL,
    tenant_id   TEXT            NOT NULL,
    provider    TEXT            NOT NULL,
    external_id TEXT,
    strategy    TEXT,           -- 'api_first' | 'ical_fallback' | 'skip' | 'dry_run'
    status      TEXT            NOT NULL
                CHECK (status IN ('ok', 'failed', 'dry_run', 'skipped')),
    http_status INTEGER,
    message     TEXT,
    synced_at   TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------
-- Lookup by booking (most common query)
CREATE INDEX IF NOT EXISTS idx_osl_booking_id
    ON outbound_sync_log (booking_id);

-- Lookup by tenant + status (operator triage)
CREATE INDEX IF NOT EXISTS idx_osl_tenant_status
    ON outbound_sync_log (tenant_id, status);

-- Lookup by tenant + synced_at (latest runs)
CREATE INDEX IF NOT EXISTS idx_osl_tenant_synced_at
    ON outbound_sync_log (tenant_id, synced_at DESC);

-- -----------------------------------------------------------------------
-- Row-Level Security
-- -----------------------------------------------------------------------
ALTER TABLE outbound_sync_log ENABLE ROW LEVEL SECURITY;

-- Service role: full access (write from executor + Phase 145 read inspector)
DROP POLICY IF EXISTS "service_role_all_osl" ON outbound_sync_log;
CREATE POLICY "service_role_all_osl"
    ON outbound_sync_log
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users: read their own tenant's rows only
DROP POLICY IF EXISTS "authenticated_read_osl" ON outbound_sync_log;
CREATE POLICY "authenticated_read_osl"
    ON outbound_sync_log
    FOR SELECT
    TO authenticated
    USING (tenant_id = current_setting('request.jwt.claims', true)::jsonb->>'sub');

-- -----------------------------------------------------------------------
-- Table comment
-- -----------------------------------------------------------------------
COMMENT ON TABLE outbound_sync_log IS
    'Phase 144 — Outbound Sync Result Persistence. '
    'Append-only audit log of every ExecutionResult produced by outbound_executor. '
    'One row per AdapterResult / per action in each sync plan execution. '
    'Never updated — only inserted. Read API added in Phase 145.';
