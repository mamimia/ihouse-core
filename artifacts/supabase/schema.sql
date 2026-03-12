-- ============================================================
-- iHouse Core — Supabase Schema Export
-- Exported: Phase 284 (2026-03-12)
-- Tables: 34
-- Source: live Supabase DB (information_schema.columns)
-- ============================================================

-- ENUM
CREATE TYPE IF NOT EXISTS public.event_kind AS ENUM (
  'BOOKING_CREATED', 'BOOKING_UPDATED', 'BOOKING_CANCELED',
  'BOOKING_CHECKED_IN', 'BOOKING_CHECKED_OUT', 'BOOKING_SYNC_ERROR',
  'AVAILABILITY_UPDATED', 'RATE_UPDATED', 'STATE_UPSERT',
  'envelope_received', 'envelope_applied', 'envelope_rejected',
  'envelope_error', 'BOOKING_AMENDED'
);

-- ai_audit_log
CREATE TABLE IF NOT EXISTS ai_audit_log (
  id                             BIGINT NOT NULL DEFAULT nextval('ai_audit_log_id_seq'::regclass),
  tenant_id                      TEXT NOT NULL,
  endpoint                       TEXT NOT NULL,
  request_type                   TEXT NOT NULL,
  input_summary                  TEXT NOT NULL DEFAULT ''::text,
  output_summary                 TEXT NOT NULL DEFAULT ''::text,
  generated_by                   TEXT NOT NULL DEFAULT 'heuristic'::text,
  entity_type                    TEXT,
  entity_id                      TEXT,
  language                       TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- audit_events
CREATE TABLE IF NOT EXISTS audit_events (
  id                             BIGINT NOT NULL DEFAULT nextval('audit_events_id_seq'::regclass),
  tenant_id                      TEXT NOT NULL,
  actor_id                       TEXT NOT NULL,
  action                         TEXT NOT NULL,
  entity_type                    TEXT NOT NULL,
  entity_id                      TEXT NOT NULL,
  payload                        JSONB NOT NULL DEFAULT '{}'::jsonb,
  occurred_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- booking_financial_facts
CREATE TABLE IF NOT EXISTS booking_financial_facts (
  id                             BIGINT NOT NULL DEFAULT nextval('booking_financial_facts_id_seq'::regclass),
  booking_id                     TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  provider                       TEXT NOT NULL,
  total_price                    NUMERIC,
  currency                       CHAR(3),
  ota_commission                 NUMERIC,
  taxes                          NUMERIC,
  fees                           NUMERIC,
  net_to_property                NUMERIC,
  source_confidence              TEXT NOT NULL,
  raw_financial_fields           JSONB NOT NULL DEFAULT '{}'::jsonb,
  event_kind                     TEXT NOT NULL,
  recorded_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- booking_flags
CREATE TABLE IF NOT EXISTS booking_flags (
  id                             BIGINT NOT NULL DEFAULT nextval('booking_flags_id_seq'::regclass),
  booking_id                     TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  is_vip                         BOOLEAN NOT NULL DEFAULT false,
  is_disputed                    BOOLEAN NOT NULL DEFAULT false,
  needs_review                   BOOLEAN NOT NULL DEFAULT false,
  operator_note                  TEXT,
  flagged_by                     TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- booking_overrides
CREATE TABLE IF NOT EXISTS booking_overrides (
  override_id                    TEXT NOT NULL,
  booking_id                     TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  status                         TEXT NOT NULL,
  required_approver_role         TEXT,
  conflicts_json                 TEXT NOT NULL,
  request_id                     TEXT,
  created_at_ms                  BIGINT NOT NULL,
  updated_at_ms                  BIGINT NOT NULL
);

-- booking_state
CREATE TABLE IF NOT EXISTS booking_state (
  booking_id                     TEXT NOT NULL,
  version                        INTEGER NOT NULL,
  state_json                     JSONB NOT NULL,
  updated_at_ms                  BIGINT NOT NULL,
  last_event_id                  TEXT,
  last_envelope_id               TEXT,
  tenant_id                      TEXT,
  source                         TEXT,
  reservation_ref                TEXT,
  property_id                    TEXT,
  check_in                       DATE,
  check_out                      DATE,
  status                         TEXT,
  guest_id                       UUID
);

-- bookings
CREATE TABLE IF NOT EXISTS bookings (
  booking_id                     TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  external_ref                   TEXT,
  start_date                     TEXT NOT NULL,
  end_date                       TEXT NOT NULL,
  status                         TEXT NOT NULL,
  guest_name                     TEXT,
  created_at_ms                  BIGINT NOT NULL,
  updated_at_ms                  BIGINT NOT NULL
);

-- conflict_tasks
CREATE TABLE IF NOT EXISTS conflict_tasks (
  conflict_task_id               TEXT NOT NULL,
  booking_id                     TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  status                         TEXT NOT NULL,
  priority                       TEXT,
  conflicts_json                 TEXT NOT NULL,
  request_id                     TEXT,
  created_at_ms                  BIGINT NOT NULL,
  updated_at_ms                  BIGINT NOT NULL
);

-- envelope_gate
CREATE TABLE IF NOT EXISTS envelope_gate (
  envelope_id                    TEXT NOT NULL,
  received_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload_json                   JSONB
);

-- event_kind_registry
CREATE TABLE IF NOT EXISTS event_kind_registry (
  event_kind                     event_kind NOT NULL,
  version                        INTEGER NOT NULL,
  is_external                    BOOLEAN NOT NULL DEFAULT false,
  is_active                      BOOLEAN NOT NULL DEFAULT true,
  required_keys                  TEXT[],
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- event_kind_versions
CREATE TABLE IF NOT EXISTS event_kind_versions (
  kind                           event_kind NOT NULL,
  version                        INTEGER NOT NULL,
  required_payload_fields        TEXT[] NOT NULL DEFAULT '{}'::text[]
);

-- event_log
CREATE TABLE IF NOT EXISTS event_log (
  event_id                       TEXT NOT NULL,
  kind                           event_kind NOT NULL,
  occurred_at                    TIMESTAMPTZ NOT NULL,
  payload_json                   JSONB NOT NULL,
  envelope_id                    TEXT
);

-- event_log_archive
CREATE TABLE IF NOT EXISTS event_log_archive (
  event_id                       TEXT NOT NULL,
  envelope_id                    TEXT NOT NULL,
  kind                           TEXT NOT NULL,
  occurred_at                    TIMESTAMPTZ NOT NULL,
  payload_json                   JSONB NOT NULL
);

-- exchange_rates
CREATE TABLE IF NOT EXISTS exchange_rates (
  id                             BIGINT NOT NULL DEFAULT nextval('exchange_rates_id_seq'::regclass),
  from_currency                  TEXT NOT NULL,
  to_currency                    TEXT NOT NULL,
  rate                           NUMERIC NOT NULL,
  recorded_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  source                         TEXT
);

-- guest_feedback
CREATE TABLE IF NOT EXISTS guest_feedback (
  id                             UUID NOT NULL DEFAULT gen_random_uuid(),
  booking_id                     TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  rating                         SMALLINT NOT NULL,
  category                       TEXT,
  comment                        TEXT,
  submitted_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
  verification_token             TEXT NOT NULL,
  token_used                     BOOLEAN NOT NULL DEFAULT false
);

-- guest_messages_log
CREATE TABLE IF NOT EXISTS guest_messages_log (
  id                             UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id                      TEXT NOT NULL,
  booking_id                     TEXT NOT NULL,
  guest_id                       TEXT,
  direction                      TEXT NOT NULL DEFAULT 'OUTBOUND'::text,
  channel                        TEXT NOT NULL,
  intent                         TEXT,
  content_preview                TEXT,
  draft_id                       TEXT,
  sent_by                        TEXT,
  sent_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- guest_profile
CREATE TABLE IF NOT EXISTS guest_profile (
  id                             BIGINT NOT NULL DEFAULT nextval('guest_profile_id_seq'::regclass),
  booking_id                     TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  guest_name                     TEXT,
  guest_email                    TEXT,
  guest_phone                    TEXT,
  source                         TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- guests
CREATE TABLE IF NOT EXISTS guests (
  id                             UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id                      TEXT NOT NULL,
  full_name                      TEXT NOT NULL,
  email                          TEXT,
  phone                          TEXT,
  nationality                    TEXT,
  passport_no                    TEXT,
  notes                          TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- notification_channels
CREATE TABLE IF NOT EXISTS notification_channels (
  id                             BIGINT NOT NULL DEFAULT nextval('notification_channels_id_seq'::regclass),
  tenant_id                      TEXT NOT NULL,
  user_id                        TEXT NOT NULL,
  channel_type                   TEXT NOT NULL,
  channel_id                     TEXT NOT NULL,
  active                         BOOLEAN NOT NULL DEFAULT true,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- notification_delivery_log
CREATE TABLE IF NOT EXISTS notification_delivery_log (
  notification_delivery_id       TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  user_id                        TEXT NOT NULL,
  task_id                        TEXT,
  trigger_reason                 TEXT,
  channel_type                   TEXT NOT NULL,
  channel_id                     TEXT NOT NULL,
  status                         TEXT NOT NULL,
  error_message                  TEXT,
  dispatched_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- notifications
CREATE TABLE IF NOT EXISTS notifications (
  notification_id                TEXT NOT NULL,
  request_id                     TEXT,
  kind                           TEXT NOT NULL,
  action_type                    TEXT,
  target                         TEXT,
  reason                         TEXT,
  property_id                    TEXT,
  task_id                        TEXT,
  created_at_ms                  BIGINT NOT NULL
);

-- ota_dead_letter
CREATE TABLE IF NOT EXISTS ota_dead_letter (
  id                             BIGINT NOT NULL DEFAULT nextval('ota_dead_letter_id_seq'::regclass),
  received_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  provider                       TEXT NOT NULL DEFAULT ''::text,
  event_type                     TEXT NOT NULL DEFAULT ''::text,
  rejection_code                 TEXT NOT NULL DEFAULT ''::text,
  rejection_msg                  TEXT,
  envelope_json                  JSONB NOT NULL DEFAULT '{}'::jsonb,
  emitted_json                   JSONB,
  trace_id                       TEXT,
  replayed_at                    TIMESTAMPTZ,
  replay_result                  TEXT,
  replay_trace_id                TEXT
);

-- VIEW: ota_dlq_summary
-- (materialized view, not a table)

-- ota_ordering_buffer
CREATE TABLE IF NOT EXISTS ota_ordering_buffer (
  id                             BIGINT NOT NULL DEFAULT nextval('ota_ordering_buffer_id_seq'::regclass),
  dlq_row_id                     BIGINT NOT NULL,
  booking_id                     TEXT NOT NULL,
  event_type                     TEXT NOT NULL,
  buffered_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  status                         TEXT NOT NULL DEFAULT 'waiting'::text
);

-- outbound_sync_log
CREATE TABLE IF NOT EXISTS outbound_sync_log (
  id                             BIGINT NOT NULL DEFAULT nextval('outbound_sync_log_id_seq'::regclass),
  booking_id                     TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  provider                       TEXT NOT NULL,
  external_id                    TEXT,
  strategy                       TEXT,
  status                         TEXT NOT NULL,
  http_status                    INTEGER,
  message                        TEXT,
  synced_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- outbox
CREATE TABLE IF NOT EXISTS outbox (
  outbox_id                      TEXT NOT NULL,
  event_id                       TEXT NOT NULL,
  event_type                     TEXT NOT NULL,
  aggregate_type                 TEXT,
  aggregate_id                   TEXT,
  channel                        TEXT NOT NULL,
  action_type                    TEXT NOT NULL,
  target                         TEXT,
  payload_json                   TEXT NOT NULL,
  status                         TEXT NOT NULL,
  attempt_count                  INTEGER NOT NULL DEFAULT 0,
  next_attempt_at_ms             BIGINT NOT NULL DEFAULT 0,
  last_error                     TEXT,
  claimed_by                     TEXT,
  claimed_until_ms               BIGINT NOT NULL DEFAULT 0,
  created_at_ms                  BIGINT NOT NULL,
  updated_at_ms                  BIGINT NOT NULL
);

-- pre_arrival_queue
CREATE TABLE IF NOT EXISTS pre_arrival_queue (
  id                             BIGINT NOT NULL DEFAULT nextval('pre_arrival_queue_id_seq'::regclass),
  tenant_id                      TEXT NOT NULL,
  booking_id                     TEXT NOT NULL,
  property_id                    TEXT,
  check_in                       DATE NOT NULL,
  tasks_created                  JSONB NOT NULL DEFAULT '[]'::jsonb,
  draft_written                  BOOLEAN NOT NULL DEFAULT false,
  draft_preview                  TEXT,
  scanned_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- property_channel_map
CREATE TABLE IF NOT EXISTS property_channel_map (
  id                             BIGINT NOT NULL DEFAULT nextval('property_channel_map_id_seq'::regclass),
  tenant_id                      TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  provider                       TEXT NOT NULL,
  external_id                    TEXT NOT NULL,
  inventory_type                 TEXT NOT NULL DEFAULT 'single_unit'::text,
  sync_mode                      TEXT NOT NULL DEFAULT 'api_first'::text,
  enabled                        BOOLEAN NOT NULL DEFAULT true,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  timezone                       TEXT
);

-- provider_capability_registry
CREATE TABLE IF NOT EXISTS provider_capability_registry (
  id                             BIGINT NOT NULL DEFAULT nextval('provider_capability_registry_id_seq'::regclass),
  provider                       TEXT NOT NULL,
  tier                           TEXT NOT NULL,
  supports_api_write             BOOLEAN NOT NULL DEFAULT false,
  supports_ical_push             BOOLEAN NOT NULL DEFAULT false,
  supports_ical_pull             BOOLEAN NOT NULL DEFAULT true,
  rate_limit_per_min             INTEGER NOT NULL DEFAULT 60,
  auth_method                    TEXT NOT NULL DEFAULT 'oauth2'::text,
  write_api_base_url             TEXT,
  notes                          TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- rate_cards
CREATE TABLE IF NOT EXISTS rate_cards (
  id                             UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id                      TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  room_type                      TEXT NOT NULL,
  season                         TEXT NOT NULL,
  base_rate                      NUMERIC NOT NULL,
  currency                       TEXT NOT NULL DEFAULT 'THB'::text,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- task_templates
CREATE TABLE IF NOT EXISTS task_templates (
  id                             UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id                      TEXT NOT NULL,
  title                          TEXT NOT NULL,
  kind                           TEXT NOT NULL,
  priority                       TEXT NOT NULL DEFAULT 'normal'::text,
  estimated_minutes              INTEGER,
  trigger_event                  TEXT,
  instructions                   TEXT,
  active                         BOOLEAN NOT NULL DEFAULT true,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- tasks
CREATE TABLE IF NOT EXISTS tasks (
  task_id                        TEXT NOT NULL,
  tenant_id                      TEXT NOT NULL,
  kind                           TEXT NOT NULL,
  status                         TEXT NOT NULL,
  priority                       TEXT NOT NULL,
  urgency                        TEXT NOT NULL,
  worker_role                    TEXT NOT NULL,
  ack_sla_minutes                INTEGER NOT NULL,
  booking_id                     TEXT NOT NULL,
  property_id                    TEXT NOT NULL,
  due_date                       DATE NOT NULL,
  title                          TEXT NOT NULL,
  description                    TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes                          JSONB NOT NULL DEFAULT '[]'::jsonb,
  canceled_reason                TEXT
);

-- tenant_permissions
CREATE TABLE IF NOT EXISTS tenant_permissions (
  id                             BIGINT NOT NULL DEFAULT nextval('tenant_permissions_id_seq'::regclass),
  tenant_id                      TEXT NOT NULL,
  user_id                        TEXT NOT NULL,
  role                           TEXT NOT NULL,
  permissions                    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- worker_availability
CREATE TABLE IF NOT EXISTS worker_availability (
  id                             UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id                      TEXT NOT NULL,
  worker_id                      TEXT NOT NULL,
  date                           DATE NOT NULL,
  start_time                     TIME,
  end_time                       TIME,
  status                         TEXT NOT NULL DEFAULT 'AVAILABLE'::text,
  notes                          TEXT,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now()
);
