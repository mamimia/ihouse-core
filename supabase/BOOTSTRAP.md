# iHouse Core — Supabase Bootstrap Guide

> This document explains how to reproduce a fresh Supabase database from scratch.
> Last updated: Phase 284 (2026-03-12)
>
> **Live Supabase: 33 tables + 1 view (`ota_dlq_summary`), 29 migrations, all RLS enabled.**

## Complete Migration Sequence

Apply migrations **in this exact order** to a fresh Supabase project:

### Step 1 — Core Schema Baseline (Phase 274)

```
supabase/migrations/20260311220000_phase274_core_schema_baseline.sql
```

Creates all canonical tables from Phases 1-50:
- `event_log` — append-only event chronicle (immutable)
- `booking_state` — derived projection (never write directly)
- `event_kind_registry` — allowlist for canonical event kinds
- `event_kind_versions`, `bookings`, `booking_overrides`, `conflict_tasks`
- `envelope_gate`, `event_log_archive`, `notifications`, `outbox`

**Then apply `artifacts/supabase/schema.sql` in the Supabase SQL editor** to install the RPC functions:
- `apply_envelope` — the canonical write gate (**never bypass this**)
- `apply_event`, `validate_emitted_event`
- `read_booking_by_id`, `read_booking_by_business_key`

### Step 2 — Application Table Migrations (Phases 135–171)

Apply in order:
```
migrations/phase_135_property_channel_map.sql
migrations/phase_136_provider_capability_registry.sql
migrations/phase_144_outbound_sync_log.sql
migrations/phase_150_property_channel_map_timezone.sql
migrations/phase_156_properties_table.sql
migrations/phase_159_guest_profile.sql
migrations/phase_160_booking_flags.sql
migrations/phase_161_exchange_rates.sql
migrations/phase_165_tenant_permissions.sql
migrations/phase_168_notification_channels.sql
migrations/phase_171_admin_audit_log.sql
```

### Step 3 — Supabase Timestamped Migrations (Phases 39–248)

These are in `supabase/migrations/` with timestamps. Apply in filename order:
```
supabase/migrations/20260308174500_phase39_dlq_replay_columns.sql
supabase/migrations/20260308184200_phase40_dlq_summary_view.sql
supabase/migrations/20260308192000_phase44_ordering_buffer.sql
supabase/migrations/20260308210000_phase50_step2_apply_envelope_amended.sql
supabase/migrations/20260309180000_phase114_tasks_table.sql
supabase/migrations/20260311120000_phase230_ai_audit_log.sql
supabase/migrations/20260311143000_phase232_pre_arrival_queue.sql
supabase/migrations/20260311150000_phase234_worker_availability.sql
supabase/migrations/20260311152100_phase236_guest_messages_log.sql
supabase/migrations/20260311164500_phase246_rate_cards.sql
supabase/migrations/20260311165100_phase247_guest_feedback.sql
supabase/migrations/20260311165500_phase248_task_templates.sql
supabase/migrations/20260311220000_phase274_core_schema_baseline.sql
supabase/migrations/20260311230000_phase277_event_kind_booking_amended.sql  ← Phase 277 addendum
supabase/migrations/20260311230100_phase277_booking_state_guest_id.sql       ← Phase 277 addendum
```

## Environment Variables Required

```env
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
IHOUSE_JWT_SECRET=<at-least-32-bytes>
IHOUSE_API_KEY=<your-api-key>
```

## Cardinal Rules

1. **Never write directly to `event_log` or `booking_state`** from application code.  
   All writes go through `apply_envelope` RPC.

2. **Never skip Step 1** — the RPC functions depend on the enum and tables from the baseline.

3. **RLS** — enable Row Level Security on `booking_state` and `event_log` after applying migrations.  
   See `docs/archive/phases/phase-199-spec.md` for policy details.

4. **The `apply_envelope` function is the single write authority** — its definition lives in  
   `artifacts/supabase/schema.sql`. Keep this file updated every Platform Checkpoint.
