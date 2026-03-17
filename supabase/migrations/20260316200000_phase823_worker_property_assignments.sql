-- Phase 823: Worker-Property Assignments
-- Maps workers to their assigned properties for role-scoped task filtering.
-- Workers can be assigned multiple properties; properties can have multiple workers.

CREATE TABLE IF NOT EXISTS worker_property_assignments (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    property_id     TEXT NOT NULL,
    worker_role     TEXT NOT NULL DEFAULT 'GENERAL_STAFF',
    is_primary      BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Each worker has at most one assignment per property per role
    CONSTRAINT uq_worker_property_role UNIQUE (tenant_id, user_id, property_id, worker_role)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_wpa_tenant_user ON worker_property_assignments(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_wpa_tenant_property ON worker_property_assignments(tenant_id, property_id);

-- Enable RLS
ALTER TABLE worker_property_assignments ENABLE ROW LEVEL SECURITY;

-- Basic RLS policy: tenant isolation
CREATE POLICY "tenant_isolation" ON worker_property_assignments
    FOR ALL USING (tenant_id = current_setting('request.jwt.claim.tenant_id', true));
