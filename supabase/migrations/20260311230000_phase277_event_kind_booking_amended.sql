-- Phase 277 — Schema Alignment: event_kind enum addendum
-- Adds BOOKING_AMENDED to the event_kind enum.
-- This value is present in the live Supabase database (Phase ~194, booking amendments feature)
-- but was absent from artifacts/supabase/schema.sql and the Phase 274 baseline migration.
--
-- Apply AFTER: 20260311220000_phase274_core_schema_baseline.sql
-- Source of truth: live Supabase DB queried at Phase 277 (2026-03-11)

ALTER TYPE "public"."event_kind" ADD VALUE IF NOT EXISTS 'BOOKING_AMENDED';
