CREATE TABLE IF NOT EXISTS events (
  row_id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL,
  ts_ms INTEGER NOT NULL,
  kind TEXT NOT NULL,
  request_json TEXT NOT NULL,
  response_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_ts_ms ON events(ts_ms);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event_id);

CREATE TABLE IF NOT EXISTS properties (
  property_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY,
  email TEXT UNIQUE,
  name TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
  booking_id TEXT PRIMARY KEY,
  property_id TEXT NOT NULL,
  external_ref TEXT,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  status TEXT NOT NULL,
  guest_name TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL,
  FOREIGN KEY(property_id) REFERENCES properties(property_id)
);

CREATE INDEX IF NOT EXISTS idx_bookings_property_dates ON bookings(property_id, start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(status);

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  property_id TEXT NOT NULL,
  booking_id TEXT,
  kind TEXT NOT NULL,
  status TEXT NOT NULL,
  due_at_ms INTEGER,
  payload_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL,
  FOREIGN KEY(property_id) REFERENCES properties(property_id),
  FOREIGN KEY(booking_id) REFERENCES bookings(booking_id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_property_status ON tasks(property_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at_ms);
