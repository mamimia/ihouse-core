-- Phase 6 hardening: claim + lease for safe multi-daemon processing

ALTER TABLE outbox ADD COLUMN claimed_by TEXT;
ALTER TABLE outbox ADD COLUMN claimed_until_ms INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_outbox_claimed_until
  ON outbox(claimed_until_ms);

CREATE INDEX IF NOT EXISTS idx_outbox_status_due_claim
  ON outbox(status, next_attempt_at_ms, claimed_until_ms);
