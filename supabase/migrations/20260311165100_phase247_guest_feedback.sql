-- Phase 247 — Guest Feedback Collection API
-- Creates the guest_feedback table for structured post-stay feedback.
--
-- Columns:
--   id             UUID PK
--   booking_id     TEXT NOT NULL — links to the booking (non-FK, cross-table reference)
--   tenant_id      TEXT NOT NULL — tenant isolation
--   property_id    TEXT NOT NULL — which property this feedback is for (denormalized for queries)
--   rating         SMALLINT NOT NULL — 1-5 star rating (CHECK constraint)
--   category       TEXT — e.g. "cleanliness", "location", "value", "communication"
--   comment        TEXT — free-text comment (nullable)
--   submitted_at   TIMESTAMPTZ NOT NULL DEFAULT now()
--   verification_token  TEXT NOT NULL — token-gated submission (no user auth required)
--   token_used     BOOLEAN NOT NULL DEFAULT FALSE — idempotency guard
--
-- NPS derivation rule (applied in query layer):
--   rating 5       → Promoter
--   rating 4       → Passive
--   rating 1-3     → Detractor
--   NPS = (Promoters% - Detractors%) × 100
--
-- RLS: enabled. Tenant scoped on admin reads.
-- Guest submission endpoint is unauthenticated (verification_token-gated).

CREATE TABLE IF NOT EXISTS guest_feedback (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    booking_id          TEXT NOT NULL,
    tenant_id           TEXT NOT NULL,
    property_id         TEXT NOT NULL,
    rating              SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    category            TEXT,
    comment             TEXT,
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    verification_token  TEXT NOT NULL,
    token_used          BOOLEAN NOT NULL DEFAULT FALSE
);

-- Prevent double submission per token
CREATE UNIQUE INDEX IF NOT EXISTS guest_feedback_token_uq
    ON guest_feedback (verification_token);

-- Fast admin queries: by tenant + property
CREATE INDEX IF NOT EXISTS guest_feedback_tenant_property_idx
    ON guest_feedback (tenant_id, property_id);

-- Fast admin queries: by booking
CREATE INDEX IF NOT EXISTS guest_feedback_booking_idx
    ON guest_feedback (tenant_id, booking_id);

-- Enable RLS (admin reads scoped by tenant_id; guest POST bypasses via service role key)
ALTER TABLE guest_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY guest_feedback_tenant_isolation ON guest_feedback
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));
