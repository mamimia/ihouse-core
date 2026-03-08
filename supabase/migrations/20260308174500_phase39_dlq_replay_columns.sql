-- Phase 39: Add replay tracking columns to ota_dead_letter
-- Allows recording the outcome of a controlled manual replay attempt.

ALTER TABLE public.ota_dead_letter
  ADD COLUMN IF NOT EXISTS replayed_at     timestamptz,
  ADD COLUMN IF NOT EXISTS replay_result   text,
  ADD COLUMN IF NOT EXISTS replay_trace_id text;

COMMENT ON COLUMN public.ota_dead_letter.replayed_at     IS 'Timestamp of the last replay attempt. NULL means not yet replayed.';
COMMENT ON COLUMN public.ota_dead_letter.replay_result   IS 'Result of the last replay attempt: APPLIED, ALREADY_APPLIED, ALREADY_EXISTS, REJECTED, SKILL_ERROR, etc.';
COMMENT ON COLUMN public.ota_dead_letter.replay_trace_id IS 'Trace ID used for the replay envelope idempotency key.';
