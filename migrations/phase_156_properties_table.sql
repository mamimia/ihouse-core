-- Phase 156 — Property Metadata Table
-- Canonical store for property display information.
-- All UI surfaces (Operations Dashboard, Worker Mobile View, Manager Booking View) read from this table.

CREATE TABLE IF NOT EXISTS properties (
    id             BIGSERIAL PRIMARY KEY,
    property_id    TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,
    display_name   TEXT,
    timezone       TEXT NOT NULL DEFAULT 'UTC',
    base_currency  CHAR(3) NOT NULL DEFAULT 'USD',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, property_id)
);

-- RLS: Tenant isolation
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;

CREATE POLICY "properties_tenant_isolation"
    ON properties
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true));

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_properties_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER properties_updated_at_trigger
    BEFORE UPDATE ON properties
    FOR EACH ROW EXECUTE FUNCTION update_properties_updated_at();

-- Index for fast tenant-scoped lookups
CREATE INDEX IF NOT EXISTS idx_properties_tenant_property
    ON properties (tenant_id, property_id);
