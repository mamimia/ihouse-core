-- Phase 6: Outbox table for deterministic side-effects delivery
-- The outbox is a projection of immutable events into "deliverable" tasks.

CREATE TABLE IF NOT EXISTS outbox (
  outbox_id TEXT PRIMARY KEY,

  -- Source event identity (for deterministic rebuild & idempotency)
  event_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  aggregate_type TEXT,
  aggregate_id TEXT,

  -- Target delivery
  channel TEXT NOT NULL,         -- e.g. "notification", "webhook", "email", "sms"
  action_type TEXT NOT NULL,     -- e.g. "task_assigned", "task_completed", "booking_conflict"
  target TEXT,                   -- destination identifier (url, user_id, etc)
  payload_json TEXT NOT NULL,    -- JSON string (immutable payload)

  -- Delivery state machine
  status TEXT NOT NULL,          -- "pending" | "sent" | "failed"
  attempt_count INTEGER NOT NULL DEFAULT 0,
  next_attempt_at_ms INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,

  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

-- Never enqueue the same "delivery intent" twice for the same event + action
CREATE UNIQUE INDEX IF NOT EXISTS ux_outbox_event_action
  ON outbox(event_id, channel, action_type, COALESCE(target, ''));

CREATE INDEX IF NOT EXISTS idx_outbox_status_next_attempt
  ON outbox(status, next_attempt_at_ms);

CREATE INDEX IF NOT EXISTS idx_outbox_event_id
  ON outbox(event_id);
