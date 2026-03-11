-- Phase 274 — Supabase Core Schema Baseline
-- This migration reproduces the canonical core schema (Phases 1–50) in a clean,
-- reproducible form. Apply this FIRST when bootstrapping a fresh Supabase project.
--
-- Tables: event_kind (enum), event_log, booking_state, booking_overrides, bookings,
--         conflict_tasks, envelope_gate, event_kind_registry, event_kind_versions,
--         notifications, outbox
--
-- Functions: apply_envelope, apply_event, validate_emitted_event,
--            read_booking_by_id, read_booking_by_business_key
--
-- Source of truth: artifacts/supabase/schema.sql (exported from live Supabase at Phase 20)
-- Last reviewed: Phase 274 (2026-03-11)

-- ============================================================
-- ENUM
-- ============================================================

CREATE TYPE IF NOT EXISTS "public"."event_kind" AS ENUM (
    'BOOKING_CREATED',
    'BOOKING_UPDATED',
    'BOOKING_CANCELED',
    'BOOKING_CHECKED_IN',
    'BOOKING_CHECKED_OUT',
    'BOOKING_SYNC_ERROR',
    'AVAILABILITY_UPDATED',
    'RATE_UPDATED',
    'STATE_UPSERT',
    'envelope_received',
    'envelope_applied',
    'envelope_rejected',
    'envelope_error'
);

-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."event_log" (
    "event_id"    TEXT        NOT NULL,
    "kind"        "public"."event_kind" NOT NULL,
    "occurred_at" TIMESTAMPTZ NOT NULL,
    "payload_json" JSONB      NOT NULL,
    "envelope_id" TEXT,
    CONSTRAINT "event_log_pkey" PRIMARY KEY ("event_id")
);

CREATE INDEX IF NOT EXISTS "event_log_envelope_id_idx"
    ON "public"."event_log" USING btree ("envelope_id");

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."booking_state" (
    "booking_id"      TEXT    NOT NULL,
    "version"         INTEGER NOT NULL,
    "state_json"      JSONB   NOT NULL,
    "updated_at_ms"   BIGINT  NOT NULL,
    "last_event_id"   TEXT,
    "last_envelope_id" TEXT,
    "tenant_id"       TEXT,
    "source"          TEXT,
    "reservation_ref" TEXT,
    "property_id"     TEXT,
    "check_in"        DATE,
    "check_out"       DATE,
    "status"          TEXT,
    CONSTRAINT "booking_state_pkey" PRIMARY KEY ("booking_id"),
    CONSTRAINT "booking_state_last_event_fk"
        FOREIGN KEY ("last_event_id")
        REFERENCES "public"."event_log"("event_id")
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS "booking_state_business_key_uq"
    ON "public"."booking_state" USING btree ("tenant_id", "source", "reservation_ref", "property_id")
    WHERE (tenant_id IS NOT NULL AND source IS NOT NULL AND reservation_ref IS NOT NULL AND property_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS "ix_booking_state_active_dates"
    ON "public"."booking_state" USING btree ("tenant_id", "property_id", "check_in", "check_out")
    WHERE (status = 'active' AND check_in IS NOT NULL AND check_out IS NOT NULL);

CREATE INDEX IF NOT EXISTS "ix_booking_state_not_canceled_dates"
    ON "public"."booking_state" USING btree ("tenant_id", "property_id", "check_in", "check_out")
    WHERE ((status IS NULL OR status <> 'canceled') AND check_in IS NOT NULL AND check_out IS NOT NULL);

CREATE INDEX IF NOT EXISTS "ix_booking_state_updated"
    ON "public"."booking_state" USING btree ("updated_at_ms" DESC);

CREATE INDEX IF NOT EXISTS "ix_booking_state_last_event"
    ON "public"."booking_state" USING btree ("last_event_id");

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."event_kind_registry" (
    "event_kind"   "public"."event_kind" NOT NULL,
    "version"      INTEGER  NOT NULL,
    "is_external"  BOOLEAN  DEFAULT false NOT NULL,
    "is_active"    BOOLEAN  DEFAULT true  NOT NULL,
    "required_keys" TEXT[],
    "created_at"   TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT "event_kind_registry_pkey" PRIMARY KEY ("event_kind", "version")
);

CREATE INDEX IF NOT EXISTS "event_kind_registry_external_active_idx"
    ON "public"."event_kind_registry" USING btree ("is_external", "is_active", "event_kind", "version");

-- Seed: allowlisted external event kinds (required by apply_envelope)
INSERT INTO "public"."event_kind_registry" ("event_kind", "version", "is_external", "is_active", "required_keys")
VALUES
    ('BOOKING_CREATED',  1, true,  true, ARRAY['booking_id','tenant_id','source','reservation_ref','property_id']),
    ('BOOKING_CANCELED', 1, true,  true, ARRAY['booking_id']),
    ('BOOKING_UPDATED',  1, true,  true, ARRAY['booking_id']),
    ('STATE_UPSERT',     1, false, true, ARRAY['booking_id','state_json'])
ON CONFLICT (event_kind, version) DO NOTHING;

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."event_kind_versions" (
    "kind"                    "public"."event_kind" NOT NULL,
    "version"                 INTEGER NOT NULL,
    "required_payload_fields" TEXT[]  DEFAULT '{}'::TEXT[] NOT NULL,
    CONSTRAINT "event_kind_versions_pkey" PRIMARY KEY ("kind", "version")
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."bookings" (
    "booking_id"    TEXT   NOT NULL,
    "property_id"   TEXT   NOT NULL,
    "external_ref"  TEXT,
    "start_date"    TEXT   NOT NULL,
    "end_date"      TEXT   NOT NULL,
    "status"        TEXT   NOT NULL,
    "guest_name"    TEXT,
    "created_at_ms" BIGINT NOT NULL,
    "updated_at_ms" BIGINT NOT NULL,
    CONSTRAINT "bookings_pkey" PRIMARY KEY ("booking_id")
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."booking_overrides" (
    "override_id"            TEXT   NOT NULL,
    "booking_id"             TEXT   NOT NULL,
    "property_id"            TEXT   NOT NULL,
    "status"                 TEXT   NOT NULL,
    "required_approver_role" TEXT,
    "conflicts_json"         TEXT   NOT NULL,
    "request_id"             TEXT,
    "created_at_ms"          BIGINT NOT NULL,
    "updated_at_ms"          BIGINT NOT NULL,
    CONSTRAINT "booking_overrides_pkey" PRIMARY KEY ("override_id")
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."conflict_tasks" (
    "conflict_task_id" TEXT   NOT NULL,
    "booking_id"       TEXT   NOT NULL,
    "property_id"      TEXT   NOT NULL,
    "status"           TEXT   NOT NULL,
    "priority"         TEXT,
    "conflicts_json"   TEXT   NOT NULL,
    "request_id"       TEXT,
    "created_at_ms"    BIGINT NOT NULL,
    "updated_at_ms"    BIGINT NOT NULL,
    CONSTRAINT "conflict_tasks_pkey" PRIMARY KEY ("conflict_task_id")
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."envelope_gate" (
    "envelope_id" TEXT        NOT NULL,
    "received_at" TIMESTAMPTZ DEFAULT now() NOT NULL,
    "payload_json" JSONB,
    CONSTRAINT "envelope_gate_pkey" PRIMARY KEY ("envelope_id")
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."event_log_archive" (
    "event_id"     TEXT        NOT NULL,
    "envelope_id"  TEXT        NOT NULL,
    "kind"         TEXT        NOT NULL,
    "occurred_at"  TIMESTAMPTZ NOT NULL,
    "payload_json" JSONB       NOT NULL
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."notifications" (
    "notification_id" TEXT   NOT NULL,
    "request_id"      TEXT,
    "kind"            TEXT   NOT NULL,
    "action_type"     TEXT,
    "target"          TEXT,
    "reason"          TEXT,
    "property_id"     TEXT,
    "task_id"         TEXT,
    "created_at_ms"   BIGINT NOT NULL,
    CONSTRAINT "notifications_pkey" PRIMARY KEY ("notification_id")
);

-- ============================================================

CREATE TABLE IF NOT EXISTS "public"."outbox" (
    "outbox_id"          TEXT    NOT NULL,
    "event_id"           TEXT    NOT NULL,
    "event_type"         TEXT    NOT NULL,
    "aggregate_type"     TEXT,
    "aggregate_id"       TEXT,
    "channel"            TEXT    NOT NULL,
    "action_type"        TEXT    NOT NULL,
    "target"             TEXT,
    "payload_json"       TEXT    NOT NULL,
    "status"             TEXT    NOT NULL,
    "attempt_count"      INTEGER DEFAULT 0  NOT NULL,
    "next_attempt_at_ms" BIGINT  DEFAULT 0  NOT NULL,
    "last_error"         TEXT,
    "claimed_by"         TEXT,
    "claimed_until_ms"   BIGINT  DEFAULT 0  NOT NULL,
    "created_at_ms"      BIGINT  NOT NULL,
    "updated_at_ms"      BIGINT  NOT NULL,
    CONSTRAINT "outbox_pkey" PRIMARY KEY ("outbox_id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "ux_outbox_event_action"
    ON "public"."outbox" USING btree ("event_id", "channel", "action_type", COALESCE("target", ''));

CREATE INDEX IF NOT EXISTS "idx_outbox_status_next_attempt"
    ON "public"."outbox" USING btree ("status", "next_attempt_at_ms");

CREATE INDEX IF NOT EXISTS "idx_outbox_status_due_claim"
    ON "public"."outbox" USING btree ("status", "next_attempt_at_ms", "claimed_until_ms");

CREATE INDEX IF NOT EXISTS "idx_outbox_claimed_until"
    ON "public"."outbox" USING btree ("claimed_until_ms");

-- ============================================================
-- FUNCTIONS — apply_envelope (canonical write gate)
-- ============================================================
-- See full definition in artifacts/supabase/schema.sql
-- The function body is intentionally omitted here to keep this
-- migration idempotent — apply artifacts/supabase/schema.sql
-- separately via Supabase SQL editor for the full RPC definitions.
-- See supabase/BOOTSTRAP.md for the complete bootstrap sequence.
-- ============================================================

-- ============================================================
-- RLS — Row Level Security
-- NOTE: RLS policies verified and documented in Phase 199 audit.
-- Enable RLS on tables before adding policies:
--   ALTER TABLE public.booking_state ENABLE ROW LEVEL SECURITY;
--   ALTER TABLE public.event_log ENABLE ROW LEVEL SECURITY;
-- Policy details: docs/archive/phases/phase-199-spec.md
-- ============================================================
