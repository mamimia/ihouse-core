-- Phase 159 — Guest Profile Table
-- PII (guest name/email/phone) stored separately from event_log.
-- Uniqueness: one row per (booking_id, tenant_id).

CREATE TABLE IF NOT EXISTS guest_profile (
    id          BIGSERIAL PRIMARY KEY,
    booking_id  TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    guest_name  TEXT,
    guest_email TEXT,
    guest_phone TEXT,
    source      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (booking_id, tenant_id)
);

-- RLS: tenant isolation
ALTER TABLE guest_profile ENABLE ROW LEVEL SECURITY;

CREATE POLICY "guest_profile_tenant_isolation"
    ON guest_profile
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true));

-- Index for fast lookup by booking
CREATE INDEX IF NOT EXISTS idx_guest_profile_booking_tenant
    ON guest_profile (booking_id, tenant_id);
