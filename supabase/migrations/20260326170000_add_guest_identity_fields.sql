-- Phase 890 — Guest Identity & WebRTC Document Capture
-- Adds fields to public.guests to act as the permanent identity record
-- Sets up the restricted Supabase Storage bucket `guest-documents`

ALTER TABLE public.guests
    ADD COLUMN IF NOT EXISTS document_type TEXT,
    ADD COLUMN IF NOT EXISTS passport_expiry DATE,
    ADD COLUMN IF NOT EXISTS date_of_birth DATE,
    ADD COLUMN IF NOT EXISTS document_photo_url TEXT;

COMMENT ON COLUMN public.guests.document_type IS 'PASSPORT, NATIONAL_ID, DRIVING_LICENSE, etc. Classified by OCR.';
COMMENT ON COLUMN public.guests.document_photo_url IS 'Private storage path in guest-documents bucket.';

-- Insert the storage bucket if not exists
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('guest-documents', 'guest-documents', false, 10485760, ARRAY['image/jpeg', 'image/png', 'image/webp', 'application/pdf'])
ON CONFLICT (id) DO UPDATE SET public = false;

-- Minimal RLS Policy for storage.objects (if using Supabase Auth natively)
-- Since we use service_role from the backend to upload, we only need to ensure public access is blocked.
-- The backend fetches short-lived signed URLs for Admin viewing.
