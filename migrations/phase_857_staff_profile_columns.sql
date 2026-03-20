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

-- Fix: access_tokens.token_type CHECK constraint was missing 'staff_onboard'.
-- Phase 856B introduced TokenType.STAFF_ONBOARD but did not update the DB
-- constraint, causing silent insert failures.
ALTER TABLE public.access_tokens DROP CONSTRAINT IF EXISTS access_tokens_token_type_check;
ALTER TABLE public.access_tokens ADD CONSTRAINT access_tokens_token_type_check
  CHECK (token_type = ANY (ARRAY['invite'::text, 'onboard'::text, 'staff_onboard'::text]));

-- Optional: backfill existing data from comm_preference JSONB
-- Uncomment and run separately if you want to migrate existing records:
--
-- UPDATE public.tenant_permissions
-- SET
--   date_of_birth = comm_preference->>'date_of_birth',
--   id_photo_url = comm_preference->>'id_photo_url'
-- WHERE comm_preference->>'date_of_birth' IS NOT NULL
--    OR comm_preference->>'id_photo_url' IS NOT NULL;
