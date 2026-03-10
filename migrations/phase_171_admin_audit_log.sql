-- Phase 171 — Admin Audit Log
-- Permanent, append-only compliance trail for every admin action.
-- NEVER update or delete rows in this table.

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    TEXT        NOT NULL,
    actor_user_id TEXT       NOT NULL,
    action       TEXT        NOT NULL,
    -- e.g. 'grant_permission', 'revoke_permission', 'upsert_provider',
    --       'patch_provider', 'replay_dlq', 'update_permission_role'
    target_type  TEXT        NOT NULL,
    -- e.g. 'permission', 'provider', 'dlq_entry', 'booking'
    target_id    TEXT        NOT NULL,
    -- user_id, provider name, envelope_id, booking_id, etc.
    before_state JSONB,
    after_state  JSONB,
    metadata     JSONB       NOT NULL DEFAULT '{}',
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Never allow UPDATE or DELETE (enforced at app layer; DDL comment for operators)
COMMENT ON TABLE admin_audit_log IS
    'Append-only compliance trail for admin actions. Never UPDATE or DELETE rows.';

-- Tenant isolation index
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_tenant_id
    ON admin_audit_log (tenant_id, occurred_at DESC);

-- Actor lookup (who did what)
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_actor
    ON admin_audit_log (tenant_id, actor_user_id, occurred_at DESC);

-- Target lookup (what happened to a specific entity)
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_target
    ON admin_audit_log (tenant_id, target_type, target_id, occurred_at DESC);

-- Action filter
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action
    ON admin_audit_log (tenant_id, action, occurred_at DESC);

-- RLS: tenants only see their own audit rows
ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY admin_audit_log_tenant_isolation ON admin_audit_log
    USING (tenant_id = current_setting('app.tenant_id', true));
