-- Phase 862 P14 Migration: Add user_id to intake_requests
-- =============================================
-- Links intake requests to Supabase Auth identity.
-- When a signed-in user submits via /get-started, their Supabase Auth UUID
-- is stored here for later Submitter→Owner transition.
-- Nullable: anonymous submissions (no JWT) are still accepted.
-- =============================================

-- Add user_id column (nullable — anonymous submissions are valid)
ALTER TABLE public.intake_requests
    ADD COLUMN IF NOT EXISTS user_id text;

-- Index for efficient lookup by user_id
CREATE INDEX IF NOT EXISTS idx_intake_requests_user_id
    ON public.intake_requests (user_id)
    WHERE user_id IS NOT NULL;

COMMENT ON COLUMN public.intake_requests.user_id IS
    'Phase 862 P14: Supabase Auth UUID of the submitter. '
    'NULL for anonymous submissions. Used for Submitter→Owner transition.';
