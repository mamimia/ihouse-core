-- Phase 844: Staff Self-Onboarding API
-- Table for managing self-onboarding requests

CREATE TABLE IF NOT EXISTS staff_onboarding_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending_submission', -- pending_submission, pending_confirm, approved, rejected
    
    full_name TEXT,
    email TEXT,
    phone TEXT,
    emergency_contact TEXT,
    photo_url TEXT,
    comm_preference JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMPTZ DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_staff_onboard_tenant ON staff_onboarding_requests (tenant_id, status);

ALTER TABLE staff_onboarding_requests ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'staff_onboarding_requests'
      AND policyname = 'service_role_bypass'
  ) THEN
    EXECUTE $pol$
      CREATE POLICY service_role_bypass
        ON staff_onboarding_requests
        FOR ALL
        TO service_role
        USING (true)
        WITH CHECK (true)
    $pol$;
  END IF;
END
$$;
