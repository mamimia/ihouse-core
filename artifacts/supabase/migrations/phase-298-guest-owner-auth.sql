-- Phase 298 — Guest Portal + Owner Portal Real Authentication
-- Creates: guest_tokens, owner_portal_access
-- Replaces stub token validation with cryptographically signed guest tokens.
-- Adds owner_portal_access for property-level ownership grants.

-- ---------------------------------------------------------------------------
-- guest_tokens
-- ---------------------------------------------------------------------------
-- Issued server-side for a specific booking_ref + email combination.
-- token_hash: SHA-256 of the raw token (never stored in plaintext).
-- Expired or used tokens are soft-deleted (revoked_at set).

CREATE TABLE IF NOT EXISTS public.guest_tokens (
    token_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_ref     TEXT        NOT NULL,
    tenant_id       TEXT        NOT NULL,            -- issuing tenant_id
    guest_email     TEXT,                            -- optional: who the token was sent to
    token_hash      TEXT        UNIQUE NOT NULL,     -- SHA-256 hex of the raw token
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_guest_tokens_booking_ref
    ON public.guest_tokens(booking_ref);

CREATE INDEX IF NOT EXISTS idx_guest_tokens_tenant_id
    ON public.guest_tokens(tenant_id);

-- ---------------------------------------------------------------------------
-- owner_portal_access
-- ---------------------------------------------------------------------------
-- Maps owner tenant_ids to the properties they are allowed to view.
-- Access is granted by an admin (operator) and scoped to specific property_ids.
-- role: 'owner' | 'viewer' (viewers = read-only, no financial data)

CREATE TABLE IF NOT EXISTS public.owner_portal_access (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT        NOT NULL,            -- operator JWT sub (issuer)
    owner_id        TEXT        NOT NULL,            -- owner's tenant_id (grantee)
    property_id     TEXT        NOT NULL,
    role            TEXT        NOT NULL DEFAULT 'owner'
                    CHECK (role IN ('owner', 'viewer')),
    granted_by      TEXT        NOT NULL,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ,
    UNIQUE (owner_id, property_id)
);

CREATE INDEX IF NOT EXISTS idx_owner_portal_access_owner_id
    ON public.owner_portal_access(owner_id)
    WHERE revoked_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_owner_portal_access_property_id
    ON public.owner_portal_access(property_id)
    WHERE revoked_at IS NULL;
