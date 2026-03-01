PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS event_log (
  event_id     TEXT PRIMARY KEY,
  envelope_id  TEXT NOT NULL,
  kind         TEXT NOT NULL,
  occurred_at  TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_eventlog_envelope_received
ON event_log(envelope_id)
WHERE kind = 'envelope_received';

CREATE INDEX IF NOT EXISTS ix_eventlog_envelope
ON event_log(envelope_id);
