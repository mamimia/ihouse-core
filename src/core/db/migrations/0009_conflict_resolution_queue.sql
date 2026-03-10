-- Phase 184 — Booking Conflict Auto-Resolution Engine
-- Persists ConflictTask and OverrideRequest artifacts from the skill run,
-- and the associated AuditEvent, to support operator review and resolution.

-- ConflictTask: emitted when a booking_candidate overlaps with existing ACTIVE bookings.
-- OverrideRequest: emitted when actor role is admin/ops_admin and allow_admin_override=true.
-- Each row is immutable — operators work from these tasks; no updates in place.

CREATE TABLE IF NOT EXISTS conflict_resolution_queue (
    conflict_id         TEXT        PRIMARY KEY,            -- uuid v4
    tenant_id           TEXT        NOT NULL,
    artifact_type       TEXT        NOT NULL CHECK (artifact_type IN ('ConflictTask', 'OverrideRequest')),
    type_id             TEXT,                               -- policy.conflict_task_type_id or override_request_type_id
    status              TEXT        NOT NULL DEFAULT 'Open',-- Open | Acknowledged | Resolved
    priority            TEXT,                               -- High | Normal (from skill)
    property_id         TEXT        NOT NULL,
    booking_id          TEXT        NOT NULL,
    conflicts_found     JSONB       NOT NULL DEFAULT '[]',  -- list of conflicting booking_ids
    request_id          TEXT        NOT NULL,               -- idempotency key from caller
    required_approver_role TEXT,                            -- for OverrideRequest only
    created_at          TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_crq_tenant_status
    ON conflict_resolution_queue (tenant_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_crq_booking
    ON conflict_resolution_queue (booking_id);

CREATE INDEX IF NOT EXISTS idx_crq_property
    ON conflict_resolution_queue (property_id, tenant_id);

-- Unique: one ConflictTask per (booking_id, request_id) — prevents duplicate task on replay
CREATE UNIQUE INDEX IF NOT EXISTS idx_crq_idempotency
    ON conflict_resolution_queue (booking_id, request_id, artifact_type);
