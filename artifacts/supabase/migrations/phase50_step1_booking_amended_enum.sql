-- Phase 50: Step 1 — Add BOOKING_AMENDED to event_kind enum
-- Run this first in Supabase SQL Editor
-- Project: reykggmlcehswrxjviup

ALTER TYPE public.event_kind ADD VALUE IF NOT EXISTS 'BOOKING_AMENDED';
