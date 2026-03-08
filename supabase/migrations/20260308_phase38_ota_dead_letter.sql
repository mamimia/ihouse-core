-- Phase 38: Dead Letter Queue for Failed OTA Events
-- Append-only store for OTA events rejected by apply_envelope.

CREATE TABLE IF NOT EXISTS public.ota_dead_letter (
  id              bigserial PRIMARY KEY,
  received_at     timestamptz NOT NULL DEFAULT now(),
  provider        text NOT NULL DEFAULT '',
  event_type      text NOT NULL DEFAULT '',
  rejection_code  text NOT NULL DEFAULT '',
  rejection_msg   text,
  envelope_json   jsonb NOT NULL DEFAULT '{}',
  emitted_json    jsonb,
  trace_id        text
);

COMMENT ON TABLE public.ota_dead_letter IS
  'Append-only store for OTA events rejected by apply_envelope. '
  'Preserved for investigation and future replay. '
  'Must never be used as a write path into canonical state.';

-- Allow service role to insert (from the OTA adapter layer)
ALTER TABLE public.ota_dead_letter ENABLE ROW LEVEL SECURITY;

CREATE POLICY ota_dead_letter_service_insert ON public.ota_dead_letter
  FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY ota_dead_letter_service_select ON public.ota_dead_letter
  FOR SELECT
  TO service_role
  USING (true);
