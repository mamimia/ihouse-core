-- Phase 844 v3 Migration
-- Apply in Supabase Dashboard → SQL Editor

-- 1. New columns on properties table
ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS owner_phone TEXT,
  ADD COLUMN IF NOT EXISTS owner_email TEXT,
  ADD COLUMN IF NOT EXISTS amenities JSONB NOT NULL DEFAULT '[]';

-- 2. Owners table
CREATE TABLE IF NOT EXISTS owners (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   TEXT NOT NULL,
  name        TEXT NOT NULL,
  phone       TEXT,
  email       TEXT,
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Property-owners linkage
CREATE TABLE IF NOT EXISTS property_owners (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   TEXT NOT NULL,
  owner_id    UUID NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
  property_id TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (owner_id, property_id)
);

-- 4. RLS on owners (same pattern as other tables)
ALTER TABLE owners ENABLE ROW LEVEL SECURITY;
ALTER TABLE property_owners ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users within same tenant to read/write
CREATE POLICY IF NOT EXISTS "tenant_owners_all" ON owners
  FOR ALL USING (tenant_id = current_setting('app.tenant_id', TRUE));

CREATE POLICY IF NOT EXISTS "tenant_property_owners_all" ON property_owners
  FOR ALL USING (tenant_id = current_setting('app.tenant_id', TRUE));

-- 5. Storage RLS policy on property-photos bucket
-- Allow authenticated uploads (INSERT) from browser
INSERT INTO storage.policies (bucket_id, name, definition, check_definition, operation)
VALUES (
  'property-photos',
  'authenticated_upload',
  'true',
  'true',
  'INSERT'
)
ON CONFLICT DO NOTHING;
