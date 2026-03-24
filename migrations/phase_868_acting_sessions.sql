-- Phase 868 — Acting Sessions table
-- Stores scoped admin acting sessions for the Act As capability.
-- Each row represents one admin-initiated acting session with a target role.
--
-- Trust invariant: real_admin_user_id is NEVER NULL — the real admin identity
-- is always preserved.
--
-- Production rule: This table exists in all environments but Act As endpoints
-- are gated by IHOUSE_ENV != 'production'. The table itself is harmless.

CREATE TABLE IF NOT EXISTS acting_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    real_admin_user_id  UUID NOT NULL,
    real_admin_email    TEXT NOT NULL DEFAULT '',
    acting_as_role      TEXT NOT NULL,
    acting_as_context   JSONB DEFAULT '{}'::jsonb,
    tenant_id           UUID NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at          TIMESTAMPTZ NOT NULL,
    ended_at            TIMESTAMPTZ,
    end_reason          TEXT  -- 'manual_exit' | 'expired' | 'admin_revoked'
);

-- Index for looking up active sessions by admin
CREATE INDEX IF NOT EXISTS idx_acting_sessions_admin
    ON acting_sessions (real_admin_user_id, tenant_id)
    WHERE ended_at IS NULL;

-- Index for expiry sweeping
CREATE INDEX IF NOT EXISTS idx_acting_sessions_expires
    ON acting_sessions (expires_at)
    WHERE ended_at IS NULL;
