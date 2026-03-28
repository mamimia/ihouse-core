-- Phase 972 — Guest Dossier: Add messaging/communication columns to guests table
-- These columns enable the Contact section of the Guest Dossier.

ALTER TABLE public.guests
    ADD COLUMN IF NOT EXISTS whatsapp TEXT,
    ADD COLUMN IF NOT EXISTS line_id TEXT,
    ADD COLUMN IF NOT EXISTS telegram TEXT,
    ADD COLUMN IF NOT EXISTS preferred_channel TEXT;

COMMENT ON COLUMN public.guests.whatsapp IS 'WhatsApp number or profile link.';
COMMENT ON COLUMN public.guests.line_id IS 'LINE user ID.';
COMMENT ON COLUMN public.guests.telegram IS 'Telegram username or chat ID.';
COMMENT ON COLUMN public.guests.preferred_channel IS 'Preferred contact channel: phone, email, whatsapp, line, telegram.';
