-- Enforce idempotency at the event log layer
CREATE UNIQUE INDEX IF NOT EXISTS ux_events_event_id ON events(event_id);
