-- Phase 1001: Add full early checkout context columns to booking_settlement_records.
-- The settlement record already has: is_early_checkout, original_checkout_date,
-- effective_checkout_date. We add the remaining four snapshot fields so the
-- settlement record is fully self-contained and audit-ready.
--
-- Permission invariant preserved:
--   - early_checkout_approved_by is always the admin or explicitly-authorized manager
--     who approved (captured from booking_state.early_checkout_approved_by)
--   - No OTA payout/refund model is implied; this is internal settlement only.

ALTER TABLE booking_settlement_records
    ADD COLUMN IF NOT EXISTS effective_checkout_at      TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS early_checkout_reason      TEXT,
    ADD COLUMN IF NOT EXISTS early_checkout_approved_by TEXT,
    ADD COLUMN IF NOT EXISTS early_checkout_approved_at TIMESTAMPTZ;

COMMENT ON COLUMN booking_settlement_records.effective_checkout_at
    IS 'Phase 1001: Exact TIMESTAMPTZ of approved early departure (authoritative moment).';
COMMENT ON COLUMN booking_settlement_records.early_checkout_reason
    IS 'Phase 1001: Guest-stated reason for early departure (snapshotted from booking_state).';
COMMENT ON COLUMN booking_settlement_records.early_checkout_approved_by
    IS 'Phase 1001: User ID who approved the early checkout (admin or explicitly-authorized manager).';
COMMENT ON COLUMN booking_settlement_records.early_checkout_approved_at
    IS 'Phase 1001: Timestamp when early checkout was approved.';
