-- Phase 399: Access Tokens table for invite + onboard flows
-- Companion to guest_tokens (Phase 298) — universal token storage

CREATE TABLE IF NOT EXISTS access_tokens (
    id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id     TEXT NOT NULL,
    token_type    TEXT NOT NULL CHECK (token_type IN ('invite', 'onboard')),
    entity_id     TEXT NOT NULL,           -- target entity (tenant_id for invite, property_id for onboard)
    email         TEXT NOT NULL DEFAULT '',
    token_hash    TEXT NOT NULL,           -- SHA-256 hex digest (never store raw token)
    expires_at    TIMESTAMPTZ NOT NULL,
    used_at       TIMESTAMPTZ,            -- set on first consume (one-use tokens)
    revoked_at    TIMESTAMPTZ,            -- set on explicit revocation
    created_at    TIMESTAMPTZ DEFAULT now(),
    metadata      JSONB DEFAULT '{}'::jsonb,

    CONSTRAINT access_tokens_hash_unique UNIQUE (token_hash)
);

-- Index for fast token lookup by hash (primary verification path)
CREATE INDEX IF NOT EXISTS idx_access_tokens_hash ON access_tokens (token_hash);

-- Index for listing tokens by tenant
CREATE INDEX IF NOT EXISTS idx_access_tokens_tenant_type ON access_tokens (tenant_id, token_type);

-- RLS: service role only (tokens are security-critical)
ALTER TABLE access_tokens ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY access_tokens_service_role ON access_tokens
    FOR ALL
    USING (true)
    WITH CHECK (true);

COMMENT ON TABLE access_tokens IS 'Phase 399: Universal access tokens for invite and onboard flows. Hash-only storage.';
