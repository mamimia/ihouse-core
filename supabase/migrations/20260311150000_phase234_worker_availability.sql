-- Phase 234 — Shift & Availability Scheduler
-- worker_availability: one row per (tenant_id, worker_id, date)
-- Status values: AVAILABLE | UNAVAILABLE | ON_LEAVE

CREATE TABLE IF NOT EXISTS worker_availability (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   text NOT NULL,
  worker_id   text NOT NULL,
  date        date NOT NULL,
  start_time  time,                          -- NULL = all-day
  end_time    time,                          -- NULL = all-day
  status      text NOT NULL DEFAULT 'AVAILABLE',
  notes       text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),

  -- Idempotency: one slot per worker per day per tenant
  UNIQUE (tenant_id, worker_id, date),

  CONSTRAINT worker_availability_status_check
    CHECK (status IN ('AVAILABLE', 'UNAVAILABLE', 'ON_LEAVE'))
);

ALTER TABLE worker_availability ENABLE ROW LEVEL SECURITY;

CREATE POLICY "worker_availability_service_role"
  ON worker_availability FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
