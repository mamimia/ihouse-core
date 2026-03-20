-- Phase 856B Migration: intake_requests table
-- =============================================
-- Creates the intake_requests table for structured lead capture.
-- This replaces the Formspree-to-email flow for the /get-started page.
-- No auto-provisioning; every row is subject to admin review before any
-- Pipeline A or B invite is issued.
--
-- Also documents the Supabase Auth identity-linking recommendation.
-- =============================================

-- 1. Intake requests table
CREATE TABLE IF NOT EXISTS public.intake_requests (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reference_id    text NOT NULL UNIQUE,   -- Human-readable: REQ-XXXXXXXX
    name            text NOT NULL,
    email           text NOT NULL,
    company         text,
    portfolio_size  text,
    message         text,
    source          text NOT NULL DEFAULT 'get-started',
    status          text NOT NULL DEFAULT 'pending_review',
    -- Status values: pending_review → reviewed → converted | declined
    admin_notes     text,
    converted_to    text,  -- 'invite' | 'staff_onboard' | null
    converted_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT DEFAULT now()
);

-- Trigger to keep updated_at fresh
CREATE OR REPLACE FUNCTION update_intake_requests_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS intake_requests_updated_at ON public.intake_requests;
CREATE TRIGGER intake_requests_updated_at
    BEFORE UPDATE ON public.intake_requests
    FOR EACH ROW EXECUTE FUNCTION update_intake_requests_updated_at();

-- Indexes
CREATE INDEX IF NOT EXISTS idx_intake_requests_status   ON public.intake_requests (status);
CREATE INDEX IF NOT EXISTS idx_intake_requests_email    ON public.intake_requests (email);
CREATE INDEX IF NOT EXISTS idx_intake_requests_created  ON public.intake_requests (created_at DESC);

-- RLS: only service_role (backend) can write; no public reads
ALTER TABLE public.intake_requests ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (backend uses service_role key)
-- No policies needed for service_role — it bypasses RLS by default.
-- But add explicit deny for anon so behavior is explicit:
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'intake_requests' AND policyname = 'deny_anon_all'
    ) THEN
        EXECUTE $policy$
            CREATE POLICY deny_anon_all ON public.intake_requests
            FOR ALL TO anon USING (false)
        $policy$;
    END IF;
END $$;

-- 2. SUPABASE AUTH IDENTITY LINKING — CONFIGURATION NOTE (Phase 856B)
-- =====================================================================
-- This cannot be done via SQL migration. It must be enabled in the
-- Supabase Auth settings UI or via Management API:
--
--   Dashboard → Authentication → Settings → User Management
--   ✅ Enable "Link accounts with the same email address"
--
-- Effect: When a user signs in with Google and the email matches an
-- existing email/password Supabase Auth user, Supabase merges the two
-- identities under ONE UUID instead of creating a new one.
--
-- This is the safest short-term approach to same-email identity linking
-- (Phase 856B item 5). It requires zero custom code and handles the most
-- common case (admin uses esegeve@gmail.com on Google but admin@domaniqo.com
-- for email/password).
--
-- When 856C (connected accounts) is implemented, this behavior will be
-- complemented by an explicit self-service linking surface for the case
-- where the emails are DIFFERENT across providers.
-- =====================================================================

COMMENT ON TABLE public.intake_requests IS
    'Phase 856B: Structured lead intake table. Replaces Formspree early-access flow. '
    'Populated by POST /intake/request. Admin reviews and converts rows to Pipeline A or B invites.';
