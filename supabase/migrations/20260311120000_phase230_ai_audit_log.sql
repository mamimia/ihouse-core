-- Phase 230 — AI Audit Trail
-- Append-only log of every AI copilot interaction.
-- Tenant-scoped. No foreign keys (bookings may be missing).
-- RLS: service_role only (admin/copilot layer writes; admin endpoint reads).

CREATE TABLE IF NOT EXISTS ai_audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       TEXT        NOT NULL,
    endpoint        TEXT        NOT NULL,            -- e.g. 'POST /ai/copilot/morning-briefing'
    request_type    TEXT        NOT NULL,            -- e.g. 'morning_briefing', 'task_recommendations'
    input_summary   TEXT        NOT NULL DEFAULT '', -- short human-readable summary of what was asked
    output_summary  TEXT        NOT NULL DEFAULT '', -- short summary of what was returned
    generated_by    TEXT        NOT NULL DEFAULT 'heuristic', -- 'llm' | 'heuristic'
    entity_type     TEXT,                            -- optional: 'booking', 'task', 'property', etc.
    entity_id       TEXT,                            -- optional: booking_id, task_id, property_id, etc.
    language        TEXT,                            -- requested language (if applicable)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS ix_ai_audit_log_tenant_created
    ON ai_audit_log (tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_ai_audit_log_endpoint
    ON ai_audit_log (tenant_id, endpoint);

CREATE INDEX IF NOT EXISTS ix_ai_audit_log_entity
    ON ai_audit_log (tenant_id, entity_type, entity_id)
    WHERE entity_id IS NOT NULL;

-- RLS
ALTER TABLE ai_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY ai_audit_log_service_role
    ON ai_audit_log
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
