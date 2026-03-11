-- Phase 277 — Schema Alignment: booking_state.guest_id column
-- Adds guest_id (uuid, nullable) to booking_state.
-- Phase 194 introduced this column as an optional best-effort link to guests.id.
-- It was absent from artifacts/supabase/schema.sql and the Phase 274 baseline migration.
--
-- Apply AFTER: 20260311220000_phase274_core_schema_baseline.sql
-- Source of truth: live Supabase DB queried at Phase 277 (2026-03-11)

ALTER TABLE "public"."booking_state"
    ADD COLUMN IF NOT EXISTS "guest_id" UUID;

COMMENT ON COLUMN "public"."booking_state"."guest_id" IS
    'Phase 194 — Optional best-effort link to guests.id. Null = no link. Never blocks booking mutations. Not written through apply_envelope — direct UPDATE only.';
