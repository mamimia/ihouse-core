-- Add 'draft' to the properties status check constraint
ALTER TABLE properties DROP CONSTRAINT IF EXISTS properties_status_check;
ALTER TABLE properties ADD CONSTRAINT properties_status_check
  CHECK (status IN ('draft', 'pending', 'approved', 'rejected', 'archived'));
