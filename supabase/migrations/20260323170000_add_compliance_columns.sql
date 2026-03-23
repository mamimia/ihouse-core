-- Phase 862: Add compliance/document columns to tenant_permissions
-- Supports onboarding form enrichment (ID/passport + work permit data)
ALTER TABLE public.tenant_permissions
  ADD COLUMN IF NOT EXISTS id_number text,
  ADD COLUMN IF NOT EXISTS id_expiry_date text,
  ADD COLUMN IF NOT EXISTS work_permit_photo_url text,
  ADD COLUMN IF NOT EXISTS work_permit_number text,
  ADD COLUMN IF NOT EXISTS work_permit_expiry_date text,
  ADD COLUMN IF NOT EXISTS start_date text,
  ADD COLUMN IF NOT EXISTS preferred_contact text;
