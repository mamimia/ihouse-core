-- Phase 975 — booking_checkin_photos: Index of walkthrough photos captured during check-in
-- 
-- The check-in wizard uploads photos to the guest-documents bucket but previously had
-- no DB record connecting photos → booking → room. This table is the durable index.
-- The actual bytes remain in Supabase Storage; this table stores only the reference path.

CREATE TABLE IF NOT EXISTS public.booking_checkin_photos (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   TEXT NOT NULL,
    booking_id  TEXT NOT NULL,
    property_id TEXT,
    room_label  TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    purpose     TEXT NOT NULL DEFAULT 'walkthrough',
    -- purpose values: walkthrough | meter | passport | damage
    captured_at TIMESTAMPTZ,
    uploaded_by TEXT,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.booking_checkin_photos IS
    'Index of photos captured during worker check-in. Bytes are in Supabase Storage; '
    'this table holds only the reference path + metadata. Phase 975.';

COMMENT ON COLUMN public.booking_checkin_photos.purpose IS
    'walkthrough = property area photo, meter = electricity meter, '
    'passport = guest document, damage = damage evidence at checkout';

COMMENT ON COLUMN public.booking_checkin_photos.room_label IS
    'Label for the area/room: e.g. bedroom_1, living_room, meter_reading, passport_front';

CREATE INDEX IF NOT EXISTS idx_bcp_booking_purpose
    ON public.booking_checkin_photos (tenant_id, booking_id, purpose);

CREATE INDEX IF NOT EXISTS idx_bcp_booking
    ON public.booking_checkin_photos (tenant_id, booking_id);
