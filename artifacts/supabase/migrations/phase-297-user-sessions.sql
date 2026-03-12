-- Phase 297 — Auth Session Management
-- Creates: user_sessions
-- Adds server-side session tracking on top of JWT-based auth.
-- Sessions are created on login and revoked on logout.
-- JWT remains the transport — session lookup validates the token is still live.
--
-- Invariant: tenant_id (JWT sub) remains the canonical identity.
-- This table is purely additive — no existing table modified.

CREATE TABLE IF NOT EXISTS public.user_sessions (
    session_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT        NOT NULL,            -- JWT sub claim
    token_hash      TEXT        NOT NULL UNIQUE,     -- SHA-256 hex of the raw JWT
    user_agent      TEXT,                            -- request User-Agent (for audit)
    ip_address      TEXT,                            -- request IP (for audit)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,            -- mirrors JWT exp claim
    revoked_at      TIMESTAMPTZ,                     -- NULL = active, set = revoked
    revoked_reason  TEXT                             -- 'logout' | 'admin' | 'expired'
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_tenant_id
    ON public.user_sessions(tenant_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash
    ON public.user_sessions(token_hash);

CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at
    ON public.user_sessions(expires_at)
    WHERE revoked_at IS NULL;

-- View: active (non-expired, non-revoked) sessions per tenant
CREATE OR REPLACE VIEW public.active_sessions AS
SELECT
    session_id,
    tenant_id,
    user_agent,
    ip_address,
    created_at,
    expires_at
FROM public.user_sessions
WHERE revoked_at IS NULL
  AND expires_at > NOW();
