-- Phase 136 — Provider Capability Registry
-- Defines what each OTA provider supports for outbound sync.
-- Without this table, the sync trigger cannot know whether to
-- use api_first, ical_fallback, or skip a provider entirely.
--
-- Apply in Supabase SQL editor (idempotent — safe to run multiple times).

-- -----------------------------------------------------------------------
-- Table
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS provider_capability_registry (
    id                  BIGSERIAL       PRIMARY KEY,
    provider            TEXT            NOT NULL UNIQUE,   -- e.g. 'airbnb', 'bookingcom'
    tier                TEXT            NOT NULL
                        CHECK (tier IN ('A', 'B', 'C', 'D')),
    supports_api_write  BOOLEAN         NOT NULL DEFAULT false,
    supports_ical_push  BOOLEAN         NOT NULL DEFAULT false,
    supports_ical_pull  BOOLEAN         NOT NULL DEFAULT true,
    rate_limit_per_min  INTEGER         NOT NULL DEFAULT 60,
    auth_method         TEXT            NOT NULL DEFAULT 'oauth2'
                        CHECK (auth_method IN ('oauth2', 'api_key', 'basic', 'none')),
    write_api_base_url  TEXT,                              -- nullable until enrolled
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------
-- Indexes
-- -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pcr_tier
    ON provider_capability_registry (tier);

CREATE INDEX IF NOT EXISTS idx_pcr_api_write
    ON provider_capability_registry (supports_api_write)
    WHERE supports_api_write = true;

-- -----------------------------------------------------------------------
-- updated_at trigger
-- -----------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_pcr_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_pcr_updated_at ON provider_capability_registry;
CREATE TRIGGER trg_pcr_updated_at
    BEFORE UPDATE ON provider_capability_registry
    FOR EACH ROW EXECUTE FUNCTION update_pcr_updated_at();

-- -----------------------------------------------------------------------
-- Row-Level Security
-- -----------------------------------------------------------------------
ALTER TABLE provider_capability_registry ENABLE ROW LEVEL SECURITY;

-- Service role: full access
DROP POLICY IF EXISTS "service_role_all_pcr" ON provider_capability_registry;
CREATE POLICY "service_role_all_pcr"
    ON provider_capability_registry
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users: read-only (global — not tenant-scoped, same for all tenants)
DROP POLICY IF EXISTS "authenticated_read_pcr" ON provider_capability_registry;
CREATE POLICY "authenticated_read_pcr"
    ON provider_capability_registry
    FOR SELECT
    TO authenticated
    USING (true);

-- -----------------------------------------------------------------------
-- Seed data — Tier A (full API write)
-- -----------------------------------------------------------------------
INSERT INTO provider_capability_registry
    (provider, tier, supports_api_write, supports_ical_push, supports_ical_pull,
     rate_limit_per_min, auth_method, notes)
VALUES
    ('airbnb',      'A', true,  false, true,  120, 'oauth2',  'Requires Partner Program enrollment'),
    ('bookingcom',  'A', true,  false, true,   60, 'api_key', 'Connectivity Partner API'),
    ('expedia',     'A', true,  false, true,   60, 'oauth2',  'Expedia Partner Solutions API'),
    ('vrbo',        'A', true,  false, true,   60, 'oauth2',  'Vrbo API — same credentials as Expedia'),
    ('agoda',       'A', true,  false, true,   30, 'api_key', 'Agoda Channel API')
ON CONFLICT (provider) DO NOTHING;

-- Seed data — Tier B (iCal push)
INSERT INTO provider_capability_registry
    (provider, tier, supports_api_write, supports_ical_push, supports_ical_pull,
     rate_limit_per_min, auth_method, notes)
VALUES
    ('hotelbeds',   'B', false, true,  true,   20, 'api_key', 'Hotelbeds TravelgateX iCal'),
    ('tripadvisor', 'B', false, true,  true,   15, 'api_key', 'TripAdvisor Rentals iCal push'),
    ('despegar',    'B', false, true,  true,   10, 'api_key', 'Despegar iCal push — LatAm')
ON CONFLICT (provider) DO NOTHING;

-- Seed data — Tier C (iCal pull only)
INSERT INTO provider_capability_registry
    (provider, tier, supports_api_write, supports_ical_push, supports_ical_pull,
     rate_limit_per_min, auth_method, notes)
VALUES
    ('houfy',       'C', false, false, true,    5, 'none',    'iCal pull only'),
    ('misterb_b',   'C', false, false, true,    5, 'none',    'iCal pull only'),
    ('homeawayde',  'C', false, false, true,    5, 'none',    'iCal pull only — DE/AT/CH market'),
    ('golightly',   'C', false, false, true,    5, 'none',    'iCal pull only')
ON CONFLICT (provider) DO NOTHING;

-- Seed data — Tier D (read-only / monitoring only)
INSERT INTO provider_capability_registry
    (provider, tier, supports_api_write, supports_ical_push, supports_ical_pull,
     rate_limit_per_min, auth_method, notes)
VALUES
    ('line_channel', 'D', false, false, false,  0, 'none', 'LINE escalation channel — no inventory sync'),
    ('direct',       'D', false, false, false,  0, 'none', 'Direct bookings — no channel sync needed')
ON CONFLICT (provider) DO NOTHING;

-- -----------------------------------------------------------------------
-- Table comment
-- -----------------------------------------------------------------------
COMMENT ON TABLE provider_capability_registry IS
    'Phase 136 — Provider Capability Registry. '
    'Global (not tenant-scoped). Defines what each OTA supports for outbound sync. '
    'tier A = full write API, B = iCal push, C = iCal pull, D = read-only. '
    'Seeded with all 13 known providers + 2 internal channels.';
