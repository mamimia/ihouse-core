-- Phase 44: OTA Ordering Buffer
-- Holds events that arrived out-of-order (BOOKING_NOT_FOUND rejection)
-- and links them to the booking_id they are waiting for.
-- When BOOKING_CREATED for that booking_id is applied, Phase 45 will
-- read this table and trigger controlled replay via dlq_replay.py.

CREATE TABLE IF NOT EXISTS public.ota_ordering_buffer (
  id          bigserial    PRIMARY KEY,
  dlq_row_id  bigint       NOT NULL REFERENCES public.ota_dead_letter(id),
  booking_id  text         NOT NULL,
  event_type  text         NOT NULL,
  buffered_at timestamptz  NOT NULL DEFAULT now(),
  status      text         NOT NULL DEFAULT 'waiting'
                           CHECK (status IN ('waiting', 'replayed', 'expired'))
);

COMMENT ON TABLE public.ota_ordering_buffer IS
  'Staging area for OTA events that arrived before their prerequisite BOOKING_CREATED. '
  'Each row links a DLQ row to the booking_id it depends on. '
  'Status: waiting (not yet replayed), replayed (replay succeeded), expired (TTL exceeded).';

COMMENT ON COLUMN public.ota_ordering_buffer.dlq_row_id   IS 'FK to ota_dead_letter.id — the original rejected event.';
COMMENT ON COLUMN public.ota_ordering_buffer.booking_id   IS 'booking_id the event is waiting for (must exist in booking_state before replay).';
COMMENT ON COLUMN public.ota_ordering_buffer.event_type   IS 'OTA event type: BOOKING_CANCELED, etc.';
COMMENT ON COLUMN public.ota_ordering_buffer.buffered_at  IS 'When this row was written to the buffer.';
COMMENT ON COLUMN public.ota_ordering_buffer.status       IS 'waiting | replayed | expired';

-- Index for fast lookup by booking_id + status
CREATE INDEX IF NOT EXISTS ix_ordering_buffer_booking_waiting
  ON public.ota_ordering_buffer (booking_id, status)
  WHERE status = 'waiting';

-- Row-Level Security
ALTER TABLE public.ota_ordering_buffer ENABLE ROW LEVEL SECURITY;

CREATE POLICY ota_ordering_buffer_service_insert ON public.ota_ordering_buffer
  FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY ota_ordering_buffer_service_select ON public.ota_ordering_buffer
  FOR SELECT
  TO service_role
  USING (true);

CREATE POLICY ota_ordering_buffer_service_update ON public.ota_ordering_buffer
  FOR UPDATE
  TO service_role
  USING (true);
