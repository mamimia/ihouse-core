-- Phase 842: Staff Schema Extension
-- 2026-03-18
-- Extends tenant_permissions with full staff profile fields,
-- creates staff_property_assignments join table.

-- ── 1. Extend tenant_permissions ──────────────────────────────────────────
ALTER TABLE tenant_permissions
  ADD COLUMN IF NOT EXISTS photo_url                   TEXT,
  ADD COLUMN IF NOT EXISTS address                     TEXT,
  ADD COLUMN IF NOT EXISTS emergency_contact           TEXT,
  ADD COLUMN IF NOT EXISTS comm_preference             JSONB    DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS worker_roles                TEXT[]   DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS maintenance_specializations TEXT[]   DEFAULT '{}'::text[],
  ADD COLUMN IF NOT EXISTS notes                       TEXT,
  ADD COLUMN IF NOT EXISTS is_active                   BOOLEAN  DEFAULT true;

-- Backfill is_active for existing rows
UPDATE tenant_permissions SET is_active = true WHERE is_active IS NULL;

-- ── 2. Create staff_property_assignments join table ───────────────────────
CREATE TABLE IF NOT EXISTS staff_property_assignments (
  id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    TEXT        NOT NULL,
  user_id      TEXT        NOT NULL,
  property_id  TEXT        NOT NULL,
  assigned_at  TIMESTAMPTZ DEFAULT now(),
  assigned_by  TEXT,
  UNIQUE (tenant_id, user_id, property_id)
);

-- ── 3. Indexes ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_spa_tenant_user
  ON staff_property_assignments (tenant_id, user_id);

CREATE INDEX IF NOT EXISTS idx_spa_tenant_property
  ON staff_property_assignments (tenant_id, property_id);

CREATE INDEX IF NOT EXISTS idx_tp_tenant_is_active
  ON tenant_permissions (tenant_id, is_active);

-- ── 4. RLS for staff_property_assignments ─────────────────────────────────
ALTER TABLE staff_property_assignments ENABLE ROW LEVEL SECURITY;

-- Service-role bypass (backend always uses service key)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'staff_property_assignments'
      AND policyname = 'service_role_bypass'
  ) THEN
    EXECUTE $pol$
      CREATE POLICY service_role_bypass
        ON staff_property_assignments
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true)
    $pol$;
  END IF;
END
$$;
