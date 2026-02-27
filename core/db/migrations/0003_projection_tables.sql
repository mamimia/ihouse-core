CREATE TABLE IF NOT EXISTS booking_overrides (
  override_id TEXT PRIMARY KEY,
  booking_id TEXT NOT NULL,
  property_id TEXT NOT NULL,
  status TEXT NOT NULL,
  required_approver_role TEXT,
  conflicts_json TEXT,
  request_id TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_booking_overrides_booking_id ON booking_overrides(booking_id);
CREATE INDEX IF NOT EXISTS idx_booking_overrides_status ON booking_overrides(status);

CREATE TABLE IF NOT EXISTS conflict_tasks (
  conflict_task_id TEXT PRIMARY KEY,
  booking_id TEXT NOT NULL,
  property_id TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL,
  conflicts_json TEXT,
  request_id TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conflict_tasks_booking_id ON conflict_tasks(booking_id);
CREATE INDEX IF NOT EXISTS idx_conflict_tasks_status ON conflict_tasks(status);
