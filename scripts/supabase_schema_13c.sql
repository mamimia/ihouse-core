-- Phase 13C: Supabase schema (minimal)

-- event_log
create table if not exists public.event_log (
  event_id     text primary key,
  envelope_id  text not null,
  kind         text not null,
  occurred_at  timestamptz not null,
  payload_json jsonb not null
);

create unique index if not exists ux_eventlog_envelope_received
  on public.event_log(envelope_id)
  where kind = 'envelope_received';

create index if not exists ix_eventlog_envelope
  on public.event_log(envelope_id);

-- booking_state
create table if not exists public.booking_state (
  booking_id       text primary key,
  version          integer not null,
  state_json       jsonb not null,
  updated_at_ms    bigint not null,
  last_envelope_id text
);

create index if not exists ix_booking_state_updated
  on public.booking_state(updated_at_ms desc);

create index if not exists ix_booking_state_last_env
  on public.booking_state(last_envelope_id);
