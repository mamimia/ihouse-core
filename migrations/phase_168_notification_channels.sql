-- Phase 168 — Push Notification Foundation
-- notification_channels: multi-channel registration per user
-- Channels: 'line' | 'fcm' | 'email'
-- Each user may have at most one active entry per channel_type per tenant.

CREATE TABLE IF NOT EXISTS notification_channels (
    id           BIGSERIAL PRIMARY KEY,
    tenant_id    TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    channel_type TEXT NOT NULL
        CHECK (channel_type IN ('line', 'fcm', 'email')),
    channel_id   TEXT NOT NULL,
    active       BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, user_id, channel_type)
);

-- Tenant isolation index
CREATE INDEX IF NOT EXISTS idx_notification_channels_tenant_id
    ON notification_channels (tenant_id);

-- Efficient lookup: find all active channels for a user
CREATE INDEX IF NOT EXISTS idx_notification_channels_user_active
    ON notification_channels (tenant_id, user_id, active);

-- updated_at maintenance trigger
CREATE OR REPLACE FUNCTION update_notification_channels_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notification_channels_updated_at ON notification_channels;
CREATE TRIGGER trg_notification_channels_updated_at
    BEFORE UPDATE ON notification_channels
    FOR EACH ROW
    EXECUTE FUNCTION update_notification_channels_updated_at();

-- RLS: tenants only see their own rows
ALTER TABLE notification_channels ENABLE ROW LEVEL SECURITY;

CREATE POLICY notification_channels_tenant_isolation ON notification_channels
    USING (tenant_id = current_setting('app.tenant_id', true));
