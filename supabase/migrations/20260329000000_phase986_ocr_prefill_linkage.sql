-- Phase 986 — OCR Pre-fill Linkage
-- ===================================
-- Links OCR results to the product entities they informed.
-- Both columns nullable — manual-only workflows have no OCR result.

-- ── Link OCR result to guests record ──────────────────────────────
ALTER TABLE guests
    ADD COLUMN IF NOT EXISTS ocr_result_id UUID REFERENCES ocr_results(id) ON DELETE SET NULL;

COMMENT ON COLUMN guests.ocr_result_id IS
    'OCR result that pre-filled this guest identity. NULL if manually entered.';

-- ── Link OCR result to electricity_meter_readings ─────────────────
ALTER TABLE electricity_meter_readings
    ADD COLUMN IF NOT EXISTS ocr_result_id UUID REFERENCES ocr_results(id) ON DELETE SET NULL;

COMMENT ON COLUMN electricity_meter_readings.ocr_result_id IS
    'OCR result that pre-filled this meter reading. NULL if manually entered.';

-- ── Indexes for admin audit queries ───────────────────────────────
CREATE INDEX IF NOT EXISTS idx_guests_ocr_result
    ON guests(ocr_result_id) WHERE ocr_result_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_electricity_meter_readings_ocr_result
    ON electricity_meter_readings(ocr_result_id) WHERE ocr_result_id IS NOT NULL;
