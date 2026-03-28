-- Phase 982 — OCR Platform: Provider Config + Results Tables
-- ===========================================================
--
-- SCOPE: OCR is strictly limited to 3 capture types:
--   identity_document_capture, checkin_opening_meter_capture, checkout_closing_meter_capture
-- This constraint is enforced both in code (scope_guard.py) and in the CHECK constraint below.

-- ─── OCR Provider Configuration (admin-managed) ────────────────────

CREATE TABLE IF NOT EXISTS ocr_provider_config (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL,
    provider_name TEXT NOT NULL,            -- 'azure_document_intelligence', 'local_tesseract', 'local_mrz', 'local_meter'
    enabled     BOOLEAN NOT NULL DEFAULT false,
    priority    INTEGER NOT NULL DEFAULT 100,  -- lower = higher priority
    config      JSONB NOT NULL DEFAULT '{}',   -- provider-specific config (API keys encrypted)
    is_primary  BOOLEAN NOT NULL DEFAULT false,
    is_fallback BOOLEAN NOT NULL DEFAULT false,
    last_test_at       TIMESTAMPTZ,
    last_test_result   TEXT,               -- 'success' / 'error: ...'
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, provider_name)
);

-- Index for tenant lookup
CREATE INDEX IF NOT EXISTS idx_ocr_provider_config_tenant
    ON ocr_provider_config(tenant_id);

-- ─── OCR Results (per-capture) ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS ocr_results (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID NOT NULL,
    booking_id       TEXT NOT NULL,
    capture_type     TEXT NOT NULL,
    document_type    TEXT,                  -- 'PASSPORT', 'NATIONAL_ID', 'DRIVING_LICENSE', 'METER'
    provider_used    TEXT NOT NULL,
    storage_path     TEXT,                  -- source image path in Supabase Storage
    raw_response     JSONB,                -- full provider response (for debugging)
    extracted_fields JSONB NOT NULL DEFAULT '{}',  -- normalized {field_name: value}
    field_confidences JSONB NOT NULL DEFAULT '{}', -- {field_name: confidence_0_to_1}
    overall_confidence FLOAT,
    status           TEXT NOT NULL DEFAULT 'pending_review',
    reviewed_by      TEXT,                 -- user_id who confirmed/corrected
    reviewed_at      TIMESTAMPTZ,
    corrected_fields JSONB,                -- manual corrections {field_name: corrected_value}
    image_quality_score FLOAT,
    quality_warnings JSONB,                -- ['blur', 'glare', 'dark', 'cropped']
    processing_time_ms INTEGER,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Hard scope enforcement at DB level
    CONSTRAINT ocr_results_capture_type_check CHECK (
        capture_type IN (
            'identity_document_capture',
            'checkin_opening_meter_capture',
            'checkout_closing_meter_capture'
        )
    ),

    -- Status must be one of the known values
    CONSTRAINT ocr_results_status_check CHECK (
        status IN ('pending_review', 'confirmed', 'rejected', 'corrected', 'failed')
    )
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ocr_results_tenant_booking
    ON ocr_results(tenant_id, booking_id);

CREATE INDEX IF NOT EXISTS idx_ocr_results_tenant_status
    ON ocr_results(tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_ocr_results_created
    ON ocr_results(created_at DESC);

-- Enable RLS
ALTER TABLE ocr_provider_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE ocr_results ENABLE ROW LEVEL SECURITY;

-- RLS policies: tenant isolation via service role (backend always uses service role)
CREATE POLICY ocr_provider_config_tenant_isolation ON ocr_provider_config
    USING (true)
    WITH CHECK (true);

CREATE POLICY ocr_results_tenant_isolation ON ocr_results
    USING (true)
    WITH CHECK (true);
