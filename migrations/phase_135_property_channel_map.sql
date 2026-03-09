-- Phase 135 — Property-Channel Mapping Foundation
-- Maps internal property_id to external OTA listing IDs per provider.
-- This is the master inventory linkage for the Outbound Sync Layer.
--
-- Apply in Supabase SQL editor (dashboard.supabase.com → SQL Editor)
-- or via: supabase db push
--
-- Idempotent: safe to run multiple times (IF NOT EXISTS / OR REPLACE).

-- -----------------------------------------------------------------------
-- Table
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS property_channel_map (
    id              BIGSERIAL       PRIMARY KEY,
    tenant_id       TEXT            NOT NULL,
    property_id     TEXT            NOT NULL,
    provider        TEXT            NOT NULL,
    external_id     TEXT            NOT NULL,
    inventory_type  TEXT            NOT NULL DEFAULT 'single_unit'
                    CHECK (inventory_type IN ('single_unit', 'multi_unit', 'shared')),
    sync_mode       TEXT            NOT NULL DEFAULT 'api_first'
                    CHECK (sync_mode IN ('api_first', 'ical_fallback', 'disabled')),
    enabled         BOOLEAN         NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, property_id, provider)
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_property_channel_map_tenant
    ON property_channel_map (tenant_id);

CREATE INDEX IF NOT EXISTS idx_property_channel_map_property
    ON property_channel_map (tenant_id, property_id);

CREATE INDEX IF NOT EXISTS idx_property_channel_map_provider
    ON property_channel_map (tenant_id, provider);

CREATE INDEX IF NOT EXISTS idx_property_channel_map_enabled
    ON property_channel_map (tenant_id, enabled)
    WHERE enabled = true;

-- -----------------------------------------------------------------------
-- updated_at auto-refresh trigger
-- -----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_property_channel_map_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_property_channel_map_updated_at ON property_channel_map;
CREATE TRIGGER trg_property_channel_map_updated_at
    BEFORE UPDATE ON property_channel_map
    FOR EACH ROW EXECUTE FUNCTION update_property_channel_map_updated_at();

-- -----------------------------------------------------------------------
-- Row-Level Security
-- -----------------------------------------------------------------------
ALTER TABLE property_channel_map ENABLE ROW LEVEL SECURITY;

-- Service role: full access (used by the Python API layer via service_role key)
DROP POLICY IF EXISTS "service_role_all_property_channel_map" ON property_channel_map;
CREATE POLICY "service_role_all_property_channel_map"
    ON property_channel_map
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users: read own tenant rows only (UI / client-side access)
DROP POLICY IF EXISTS "authenticated_read_own_property_channel_map" ON property_channel_map;
CREATE POLICY "authenticated_read_own_property_channel_map"
    ON property_channel_map
    FOR SELECT
    TO authenticated
    USING (tenant_id = auth.uid()::text);

-- -----------------------------------------------------------------------
-- Table comment
-- -----------------------------------------------------------------------
COMMENT ON TABLE property_channel_map IS
    'Phase 135 — Outbound Sync Layer foundation. '
    'Maps internal property_id to external OTA listing IDs per provider. '
    'sync_mode controls outbound strategy: api_first | ical_fallback | disabled. '
    'inventory_type informs locking logic: single_unit | multi_unit | shared.';
