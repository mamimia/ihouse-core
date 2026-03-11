# Phase 277 — Supabase RPC + Schema Alignment

**Status:** Closed
**Prerequisite:** Phase 276 (Real JWT Authentication Flow)
**Date Closed:** 2026-03-11

## Goal

Query the live Supabase database and compare it against `artifacts/supabase/schema.sql` (the Phase 20 truth pack) and the Phase 274 baseline migration. Identify drift and create addendum migrations to close the gaps.

## Live Schema Audit Results

Queried project `reykggmlcehswrxjviup` (ACTIVE_HEALTHY, ap-northeast-1) at Phase 277.

### Tables (28 live)
All expected tables present. ✅

### Functions (12 live)

| Function | In schema.sql | Notes |
|----------|---------------|-------|
| `apply_envelope` | ✅ | Canonical write gate — live |
| `apply_event` | ✅ | Live |
| `validate_emitted_event` | ✅ | Live |
| `read_booking_by_id` | ✅ | Live |
| `read_booking_by_business_key` | ✅ | Live |
| `rebuild_booking_state` | ❌ | **In live, not in schema.sql** — added post-Phase 50 |
| `set_tenant_permissions_updated_at` | ❌ | Trigger function — expected, not in schema.sql |
| `update_pcr_updated_at` | ❌ | Trigger function — expected |
| `update_property_channel_map_updated_at` | ❌ | Trigger function — expected |

### Schema Drift Found

| Item | Live DB | schema.sql + Phase 274 baseline | Action |
|------|---------|----------------------------------|--------|
| `event_kind` enum `BOOKING_AMENDED` | ✅ present | ❌ absent | Addendum migration created |
| `booking_state.guest_id` UUID column | ✅ present (Phase 194) | ❌ absent | Addendum migration created |
| `rebuild_booking_state` RPC | ✅ present | ❌ absent from schema.sql | Documented — update schema.sql at next Platform Checkpoint |
| `properties` table | ❌ absent from live DB | In migrations/phase_156 | Divergence — table not applied to live yet |

## Files Created

| File | Description |
|------|-------------|
| `supabase/migrations/20260311230000_phase277_event_kind_booking_amended.sql` | Adds `BOOKING_AMENDED` to event_kind enum |
| `supabase/migrations/20260311230100_phase277_booking_state_guest_id.sql` | Adds `booking_state.guest_id` UUID nullable column |
| `supabase/BOOTSTRAP.md` | Updated with Phase 277 addendum migration entries |
| `docs/archive/phases/phase-277-spec.md` | This file |

## Next Action Required (Platform Checkpoint 282)

`artifacts/supabase/schema.sql` should be re-exported from live Supabase at Phase 282 to capture:
- `BOOKING_AMENDED` enum value
- `booking_state.guest_id` column
- `rebuild_booking_state` RPC function body
- Any other changes since Phase 20 export

## apply_envelope Status

`apply_envelope` RPC is confirmed LIVE and ACTIVE in Supabase. No drift in its signature. Its body is retained from the Phase 50 export in `artifacts/supabase/schema.sql`.
