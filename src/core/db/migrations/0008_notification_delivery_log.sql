-- Phase 183 — Notification Delivery Status Tracking
-- Records every dispatch attempt (one row per ChannelAttempt) for observability.
-- Allows operators to query notification health, diagnose LINE/FCM/email failures.

CREATE TABLE IF NOT EXISTS notification_delivery_log (
    notification_delivery_id  TEXT        PRIMARY KEY,
    tenant_id                 TEXT        NOT NULL,
    user_id                   TEXT        NOT NULL,
    task_id                   TEXT,                           -- nullable: not all notifications are task-scoped
    trigger_reason            TEXT,                           -- e.g. ACK_SLA_BREACH, CRITICAL_TASK_OVERDUE
    channel_type              TEXT        NOT NULL,           -- line | fcm | email
    channel_id                TEXT        NOT NULL,           -- LINE user_id / FCM token / email address
    status                    TEXT        NOT NULL CHECK (status IN ('sent', 'failed')),
    error_message             TEXT,                           -- NULL on success, error string on failure
    dispatched_at             TIMESTAMPTZ DEFAULT now()
);

-- Query: latest delivery attempts per tenant
CREATE INDEX IF NOT EXISTS idx_ndl_tenant_at
    ON notification_delivery_log (tenant_id, dispatched_at DESC);

-- Query: failed deliveries for a user
CREATE INDEX IF NOT EXISTS idx_ndl_user_status
    ON notification_delivery_log (tenant_id, user_id, status);

-- Query: delivery history for a specific task
CREATE INDEX IF NOT EXISTS idx_ndl_task
    ON notification_delivery_log (task_id)
    WHERE task_id IS NOT NULL;
