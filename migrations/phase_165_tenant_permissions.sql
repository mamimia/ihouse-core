-- Phase 165 — Permission Model Foundation
--
-- Creates tenant_permissions table for role-based access control.
-- Roles: admin | manager | worker | owner
-- permissions JSONB stores capability flags (e.g. can_approve_owner_statements).
--
-- Applied to Supabase: 2026-03-10

CREATE TABLE IF NOT EXISTS tenant_permissions (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL
        CONSTRAINT tenant_permissions_role_check
        CHECK (role IN ('admin', 'manager', 'worker', 'owner')),
    permissions JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id)
);

-- Index for efficient per-tenant lookups
CREATE INDEX IF NOT EXISTS idx_tenant_permissions_tenant_id
    ON tenant_permissions (tenant_id);

-- Index for per-user lookups (e.g. enriching JWT)
CREATE INDEX IF NOT EXISTS idx_tenant_permissions_user_id
    ON tenant_permissions (tenant_id, user_id);

-- RLS: tenants can only see their own permission rows
ALTER TABLE tenant_permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_permissions_tenant_isolation
    ON tenant_permissions
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true));

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_tenant_permissions_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_tenant_permissions_updated_at
    BEFORE UPDATE ON tenant_permissions
    FOR EACH ROW EXECUTE FUNCTION set_tenant_permissions_updated_at();
