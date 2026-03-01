CREATE TABLE IF NOT EXISTS notifications (
  notification_id TEXT PRIMARY KEY,
  request_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  action_type TEXT NOT NULL,
  target TEXT,
  reason TEXT,
  property_id TEXT,
  task_id TEXT,
  created_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notifications_request_id ON notifications(request_id);
CREATE INDEX IF NOT EXISTS idx_notifications_kind ON notifications(kind);
CREATE INDEX IF NOT EXISTS idx_notifications_property_id ON notifications(property_id);
CREATE INDEX IF NOT EXISTS idx_notifications_task_id ON notifications(task_id);
