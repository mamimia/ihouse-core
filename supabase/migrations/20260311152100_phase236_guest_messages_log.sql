-- Phase 236 — Guest Communication History
-- guest_messages_log: one row per message sent or received per booking

CREATE TABLE IF NOT EXISTS guest_messages_log (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       text NOT NULL,
  booking_id      text NOT NULL,
  guest_id        text,
  direction       text NOT NULL DEFAULT 'OUTBOUND',  -- OUTBOUND | INBOUND
  channel         text NOT NULL,                      -- email | whatsapp | sms | line | telegram | manual
  intent          text,                               -- check_in_instructions | booking_confirmation | etc.
  content_preview text,                               -- first 300 chars of message
  draft_id        text,                               -- links to Phase 227 draft if applicable
  sent_by         text,                               -- user_id of sender
  sent_at         timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE guest_messages_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "guest_messages_log_service_role"
  ON guest_messages_log FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_guest_messages_log_booking
  ON guest_messages_log (tenant_id, booking_id, sent_at DESC);
