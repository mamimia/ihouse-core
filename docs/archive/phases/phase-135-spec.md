# Phase 135 — Property-Channel Mapping Foundation
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-09

---

## Objective

Establish the first real foundation of the Outbound Sync Layer.

`property_channel_map` is the master inventory linkage table that maps
internal `property_id` values to external OTA listing IDs per provider.
Without this mapping, the outbound sync layer cannot know which external
listings to lock when a booking is received.

## New Table: `property_channel_map`

Apply migration SQL from: `migrations/phase_135_property_channel_map.sql`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `tenant_id` | TEXT NOT NULL | from JWT sub |
| `property_id` | TEXT NOT NULL | internal ID |
| `provider` | TEXT NOT NULL | OTA provider name (open enum) |
| `external_id` | TEXT NOT NULL | provider's listing/unit ID |
| `inventory_type` | TEXT DEFAULT `single_unit` | `single_unit` \| `multi_unit` \| `shared` |
| `sync_mode` | TEXT DEFAULT `api_first` | `api_first` \| `ical_fallback` \| `disabled` |
| `enabled` | BOOLEAN DEFAULT true | |
| `created_at` | TIMESTAMPTZ | auto |
| `updated_at` | TIMESTAMPTZ | auto (trigger) |

**Unique constraint:** `(tenant_id, property_id, provider)` — one mapping per channel.
**RLS:** enabled. `service_role` = full access. `authenticated` = read own rows.

## `sync_mode` Semantics

| Value | Meaning |
|-------|---------|
| `api_first` | Use the provider's write API for availability locking (Tier A/B) |
| `ical_fallback` | Use iCal feed (degraded mode — Tier C providers) |
| `disabled` | No outbound sync for this channel |

## Endpoints

```
POST   /admin/properties/{property_id}/channels   — register mapping
GET    /admin/properties/{property_id}/channels   — list all mappings
PATCH  /admin/properties/{property_id}/channels/{provider} — update
DELETE /admin/properties/{property_id}/channels/{provider} — remove
```

**Auth:** JWT required on all endpoints.  
**409:** Returned on duplicate `(property_id, provider)` POST.  
**404:** Returned on PATCH/DELETE when mapping not found.

## Files Added / Modified

| File | Action |
|------|--------|
| `migrations/phase_135_property_channel_map.sql` | NEW — DB migration |
| `src/api/channel_map_router.py` | NEW — CRUD router |
| `tests/test_channel_map_contract.py` | NEW — 46 contract tests |
| `src/main.py` | MODIFIED — router registered, `channel-map` tag added |

## DB Migration Required

> **[!IMPORTANT]**
> Apply `migrations/phase_135_property_channel_map.sql` in the Supabase SQL editor
> before deploying to production. The table does not yet exist in production.

## Test Results

46/46 contract tests passing ✅  
Full suite: 3430 passed, 2 failed (pre-existing SQLite guards), 3 skipped.
