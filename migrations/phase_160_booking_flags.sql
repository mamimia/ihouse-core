-- Phase 160 — Booking Flags Table
-- Operator annotations on bookings (e.g. VIP, dispute, manual review).
-- Uniqueness: one row per (booking_id, tenant_id).

CREATE TABLE IF NOT EXISTS booking_flags (
    id              BIGSERIAL PRIMARY KEY,
    booking_id      TEXT        NOT NULL,
    tenant_id       TEXT        NOT NULL,
    is_vip          BOOLEAN     NOT NULL DEFAULT FALSE,
    is_disputed     BOOLEAN     NOT NULL DEFAULT FALSE,
    needs_review    BOOLEAN     NOT NULL DEFAULT FALSE,
    operator_note   TEXT,
    flagged_by      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (booking_id, tenant_id)
);

-- RLS: tenant isolation
ALTER TABLE booking_flags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "booking_flags_tenant_isolation"
    ON booking_flags
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true));

-- Index for fast lookup by booking
CREATE INDEX IF NOT EXISTS idx_booking_flags_booking_tenant
    ON booking_flags (booking_id, tenant_id);
