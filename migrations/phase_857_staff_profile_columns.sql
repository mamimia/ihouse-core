-- Phase 857 — Staff Profile PII Columns
-- =========================================
-- Moves date_of_birth and id_photo_url out of comm_preference JSONB
-- into dedicated columns on tenant_permissions.
--
-- This migration should be applied via Supabase SQL Editor.
-- It is idempotent (IF NOT EXISTS).

ALTER TABLE public.tenant_permissions
  ADD COLUMN IF NOT EXISTS date_of_birth text,
  ADD COLUMN IF NOT EXISTS id_photo_url text;

-- Optional: backfill existing data from comm_preference JSONB
-- Uncomment and run separately if you want to migrate existing records:
--
-- UPDATE public.tenant_permissions
-- SET
--   date_of_birth = comm_preference->>'date_of_birth',
--   id_photo_url = comm_preference->>'id_photo_url'
-- WHERE comm_preference->>'date_of_birth' IS NOT NULL
--    OR comm_preference->>'id_photo_url' IS NOT NULL;
