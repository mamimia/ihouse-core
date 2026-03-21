ALTER TABLE properties
  ADD COLUMN IF NOT EXISTS submitter_user_id UUID,
  ADD COLUMN IF NOT EXISTS submitter_email TEXT;

CREATE INDEX IF NOT EXISTS idx_properties_submitter
  ON properties (submitter_user_id)
  WHERE submitter_user_id IS NOT NULL;
