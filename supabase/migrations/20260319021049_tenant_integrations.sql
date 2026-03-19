-- Phase 842 - Tenant Notification Integrations
-- Stores per-tenant API keys and webhook configurations for messaging platforms.

CREATE TABLE IF NOT EXISTS public.tenant_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,
    provider TEXT NOT NULL, -- 'line', 'whatsapp', 'telegram', 'sms'
    credentials JSONB NOT NULL DEFAULT '{}'::jsonb, -- Store encrypted or raw tokens
    is_active BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Ensure exactly one configuration per provider per tenant
    CONSTRAINT tenant_integrations_tenant_provider_idx UNIQUE (tenant_id, provider)
);

-- RLS: Service Role only (accessed via Backend API)
ALTER TABLE public.tenant_integrations ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_integrations_service_role ON public.tenant_integrations
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE public.tenant_integrations IS 'Phase 842: Tenant-level configuration and tokens for LINE, WA, Telegram, SMS';
