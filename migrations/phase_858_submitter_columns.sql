-- Phase 858: Add submitter binding columns to properties table
-- These columns allow tracking who submitted a property through the
-- /get-started intake wizard, enabling admin review and contact flow.

-- Add submitter columns (nullable — existing properties won't have these)
ALTER TABLE properties 
  ADD COLUMN IF NOT EXISTS submitter_user_id UUID,
  ADD COLUMN IF NOT EXISTS submitter_email TEXT;

-- Rename existing 'pending' status to 'pending_review' for clarity
-- The 'draft' status is now used for pre-submission wizard state
UPDATE properties SET status = 'pending_review' WHERE status = 'pending';

-- Add comment for documentation
COMMENT ON COLUMN properties.submitter_user_id IS 'Phase 858: user who submitted this property via /get-started wizard';
COMMENT ON COLUMN properties.submitter_email IS 'Phase 858: contact email for the submitter';
