-- Phase 248 — Maintenance & Housekeeping Task Templates
-- Creates the task_templates table for reusable task blueprints.
--
-- Purpose: allow operators to define named task templates that describe
-- recurring maintenance or housekeeping work. Templates can be linked to
-- a trigger_event so the task engine knows when to auto-spawn tasks.
--
-- Columns:
--   id                UUID PK
--   tenant_id         TEXT NOT NULL — tenant isolation
--   title             TEXT NOT NULL — human-readable template name
--   kind              TEXT NOT NULL — maps to existing task kinds (e.g. "housekeeping", "maintenance", "inspection")
--   priority          TEXT NOT NULL DEFAULT 'normal' — "critical" | "high" | "normal" | "low"
--   estimated_minutes INTEGER — expected effort, nullable if unknown
--   trigger_event     TEXT — optional: event that auto-spawns this task
--                           (e.g. "BOOKING_CREATED", "BOOKING_CANCELED", "checkout")
--   instructions      TEXT — optional step-by-step instructions for the worker
--   active            BOOLEAN NOT NULL DEFAULT TRUE — soft-delete via deactivation
--   created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
--   updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
--
-- Constraints:
--   title unique per tenant (allows same name across tenants)
--
-- RLS: enabled, tenant-scoped.

CREATE TABLE IF NOT EXISTS task_templates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           TEXT NOT NULL,
    title               TEXT NOT NULL,
    kind                TEXT NOT NULL,
    priority            TEXT NOT NULL DEFAULT 'normal'
                        CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    estimated_minutes   INTEGER CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
    trigger_event       TEXT,
    instructions        TEXT,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique template title per tenant
CREATE UNIQUE INDEX IF NOT EXISTS task_templates_tenant_title_uq
    ON task_templates (tenant_id, title);

-- Fast lookup by tenant + trigger_event for auto-spawn queries
CREATE INDEX IF NOT EXISTS task_templates_tenant_trigger_idx
    ON task_templates (tenant_id, trigger_event)
    WHERE trigger_event IS NOT NULL;

-- Enable RLS
ALTER TABLE task_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY task_templates_tenant_isolation ON task_templates
    USING (tenant_id = current_setting('app.current_tenant_id', true))
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true));

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_task_templates_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER task_templates_updated_at_trigger
    BEFORE UPDATE ON task_templates
    FOR EACH ROW
    EXECUTE FUNCTION update_task_templates_updated_at();
