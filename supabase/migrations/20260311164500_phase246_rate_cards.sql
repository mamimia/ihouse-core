-- Phase 246 — Rate Card & Pricing Rules Engine
-- Creates the rate_cards table for storing property-specific base rates.
--
-- Columns:
--   id            UUID PK (auto-generated)
--   tenant_id     TEXT NOT NULL — tenant isolation
--   property_id   TEXT NOT NULL — which property this rate card applies to
--   room_type     TEXT NOT NULL — e.g. "standard", "deluxe", "suite"
--   season        TEXT NOT NULL — e.g. "high", "low", "shoulder", or a date range label
--   base_rate     NUMERIC(12,2) NOT NULL — base price per night in the given currency
--   currency      TEXT NOT NULL DEFAULT 'THB'
--   created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
--   updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
--
-- Constraints:
--   rate_cards_tenant_property_room_season_uq — unique per (tenant, property, room_type, season)
--   Only one active base rate per (property, room_type, season) per tenant.
--
-- RLS: Row-level security enabled — all policies scope to tenant_id.

CREATE TABLE IF NOT EXISTS rate_cards (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    property_id TEXT NOT NULL,
    room_type   TEXT NOT NULL,
    season      TEXT NOT NULL,
    base_rate   NUMERIC(12, 2) NOT NULL CHECK (base_rate >= 0),
    currency    TEXT NOT NULL DEFAULT 'THB',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique constraint: one base rate per (tenant, property, room_type, season)
ALTER TABLE rate_cards
    ADD CONSTRAINT rate_cards_tenant_property_room_season_uq
    UNIQUE (tenant_id, property_id, room_type, season);

-- Index for fast tenant-scoped queries
CREATE INDEX IF NOT EXISTS rate_cards_tenant_property_idx
    ON rate_cards (tenant_id, property_id);

-- Enable RLS
ALTER TABLE rate_cards ENABLE ROW LEVEL SECURITY;

-- RLS policy: tenant can only see/modify their own rate cards
CREATE POLICY rate_cards_tenant_isolation ON rate_cards
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- Auto-update updated_at on row update
CREATE OR REPLACE FUNCTION update_rate_cards_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER rate_cards_updated_at_trigger
    BEFORE UPDATE ON rate_cards
    FOR EACH ROW
    EXECUTE FUNCTION update_rate_cards_updated_at();
