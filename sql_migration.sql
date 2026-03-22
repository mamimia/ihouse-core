-- Function to permanently delete unapproved properties older than 90 days
CREATE OR REPLACE FUNCTION delete_stale_unapproved_properties()
RETURNS void AS $$
DECLARE
    prop_record RECORD;
BEGIN
    FOR prop_record IN 
        SELECT property_id FROM properties 
        WHERE status IN ('draft', 'pending_review', 'rejected') 
        AND updated_at < NOW() - INTERVAL '90 days'
        AND tenant_id = 'DOM-ONB-000'
    LOOP
        -- Delete marketing photos
        DELETE FROM property_marketing_photos WHERE property_id = prop_record.property_id;
        -- Delete property
        DELETE FROM properties WHERE property_id = prop_record.property_id;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Schedule the cleanup to run daily at 3:00 AM using pg_cron
-- Remove existing if any to be safe
SELECT cron.unschedule('cleanup-stale-properties');

SELECT cron.schedule(
    'cleanup-stale-properties',
    '0 3 * * *',
    'SELECT delete_stale_unapproved_properties();'
);
