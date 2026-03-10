-- Phase 150 — iCal VTIMEZONE Support
-- Adds optional timezone column to property_channel_map.
-- Used by ICalPushAdapter to emit VTIMEZONE + TZID-qualified DTSTART/DTEND.
-- When NULL: UTC behaviour unchanged (safe, backward-compatible).

ALTER TABLE property_channel_map ADD COLUMN IF NOT EXISTS timezone TEXT;
