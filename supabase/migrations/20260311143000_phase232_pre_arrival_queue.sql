-- Phase 232 — Pre-Arrival Queue
-- Tracks which bookings have been processed by pre_arrival_scanner.
-- Unique constraint ensures idempotency: one row per (tenant, booking, check_in) per scan.

CREATE TABLE IF NOT EXISTS pre_arrival_queue (
    id            BIGSERIAL PRIMARY KEY,
    tenant_id     TEXT        NOT NULL,
    booking_id    TEXT        NOT NULL,
    property_id   TEXT,
    check_in      DATE        NOT NULL,
    tasks_created JSONB       NOT NULL DEFAULT '[]',
    draft_written BOOLEAN     NOT NULL DEFAULT FALSE,
    draft_preview TEXT,
    scanned_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, booking_id, check_in)
);

CREATE INDEX IF NOT EXISTS pre_arrival_queue_tenant_checkin
    ON pre_arrival_queue (tenant_id, check_in DESC);

ALTER TABLE pre_arrival_queue ENABLE ROW LEVEL SECURITY;

-- service_role can read and write; anon cannot
CREATE POLICY "service_role_all" ON pre_arrival_queue
    FOR ALL TO service_role USING (true) WITH CHECK (true);
