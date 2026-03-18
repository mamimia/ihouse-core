-- Phase 844 — Property owner contact snapshot + amenities columns
-- Adds owner contact fields (snapshot, not canonical owner linkage)
-- Adds amenities JSONB array for property features checklist

ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS owner_phone TEXT,
  ADD COLUMN IF NOT EXISTS owner_email TEXT,
  ADD COLUMN IF NOT EXISTS amenities   JSONB NOT NULL DEFAULT '[]'::jsonb;
