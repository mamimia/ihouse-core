-- Phase 299 — Notification Dispatch Layer
-- Creates: notification_log
-- Tracks all outbound notifications (SMS, email) dispatched by iHouse Core.
-- Providers: Twilio (SMS), SendGrid (email).
-- Additive — no existing tables modified.

CREATE TABLE IF NOT EXISTS public.notification_log (
    notification_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       TEXT        NOT NULL,            -- issuing tenant_id (operator)
    channel         TEXT        NOT NULL             -- 'sms' | 'email'
                    CHECK (channel IN ('sms', 'email', 'whatsapp')),
    recipient       TEXT        NOT NULL,            -- phone or email address
    subject         TEXT,                            -- email subject (null for SMS)
    body_preview    TEXT,                            -- first 200 chars of body (PII-sanitized)
    notification_type TEXT      NOT NULL,            -- 'guest_token' | 'task_alert' | 'booking_confirm' | 'generic'
    reference_id    TEXT,                            -- booking_ref, task_id, token_id etc.
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'sent', 'failed', 'dry_run')),
    provider_id     TEXT,                            -- external message ID from provider
    error_message   TEXT,                            -- error if status = 'failed'
    sent_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_log_tenant_id
    ON public.notification_log(tenant_id);

CREATE INDEX IF NOT EXISTS idx_notification_log_recipient
    ON public.notification_log(recipient);

CREATE INDEX IF NOT EXISTS idx_notification_log_reference_id
    ON public.notification_log(reference_id)
    WHERE reference_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_notification_log_status
    ON public.notification_log(status, created_at DESC);
