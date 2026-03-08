-- Phase 40: DLQ Observability — read-only summary view
-- Groups ota_dead_letter rows by event_type and rejection_code.

CREATE OR REPLACE VIEW public.ota_dlq_summary AS
SELECT
  event_type,
  rejection_code,
  COUNT(*)                                                    AS total,
  COUNT(*) FILTER (WHERE replayed_at IS NULL)                 AS pending,
  COUNT(*) FILTER (WHERE replayed_at IS NOT NULL)             AS replayed
FROM public.ota_dead_letter
GROUP BY event_type, rejection_code
ORDER BY pending DESC, total DESC;

COMMENT ON VIEW public.ota_dlq_summary IS
  'Read-only summary of ota_dead_letter grouped by event_type and rejection_code. '
  'pending = not yet replayed. replayed = replay attempted (any result).';
