# Phase 136 — Provider Capability Registry
**Spec version:** 1.0
**Status:** Closed ✅
**Date:** 2026-03-09

---

## Objective

The second foundational layer of the Outbound Sync system.

`provider_capability_registry` is a **global** (not tenant-scoped) table that
declares what each OTA provider supports for outbound availability sync.
Before sending any availability update, the Outbound Sync Trigger (Phase 137)
consults this table to decide which strategy to use per provider.

## New Table: `provider_capability_registry`

Apply migration SQL from: `migrations/phase_136_provider_capability_registry.sql`

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `provider` | TEXT UNIQUE NOT NULL | lowercase, e.g. `airbnb` |
| `tier` | TEXT NOT NULL CHECK (A\|B\|C\|D) | |
| `supports_api_write` | BOOLEAN DEFAULT false | |
| `supports_ical_push` | BOOLEAN DEFAULT false | |
| `supports_ical_pull` | BOOLEAN DEFAULT true | |
| `rate_limit_per_min` | INTEGER DEFAULT 60 | |
| `auth_method` | TEXT CHECK oauth2\|api_key\|basic\|none | |
| `write_api_base_url` | TEXT nullable | filled after partner enrollment |
| `notes` | TEXT nullable | |
| `created_at` | TIMESTAMPTZ | auto |
| `updated_at` | TIMESTAMPTZ | auto (trigger) |

## Tier Definitions

| Tier | Meaning | Outbound Strategy |
|------|---------|-------------------|
| A | Full write API | `api_first` |
| B | iCal push only | `ical_fallback` (push) |
| C | iCal pull only | `ical_fallback` (pull on demand) |
| D | Read-only / no sync | `disabled` |

## Pre-seeded Providers

- **Tier A (5):** airbnb, bookingcom, expedia, vrbo, agoda
- **Tier B (3):** hotelbeds, tripadvisor, despegar
- **Tier C (4):** houfy, misterb_b, homeawayde, golightly
- **Tier D (2):** line_channel, direct

## Endpoints

```
GET /admin/registry/providers              — list (filters: tier, supports_api_write)
GET /admin/registry/providers/{provider}   — single record
PUT /admin/registry/providers/{provider}   — upsert (admin)
```

**Auth:** JWT required on all endpoints.  
**Global:** not tenant-scoped — same records visible to all operators.

## Files Added / Modified

| File | Action |
|------|--------|
| `migrations/phase_136_provider_capability_registry.sql` | NEW — seeded with 14 providers |
| `src/api/capability_registry_router.py` | NEW — GET list + GET single + PUT upsert |
| `tests/test_capability_registry_contract.py` | NEW — 42 contract tests |
| `src/main.py` | MODIFIED — router registered, `registry` tag added |

## DB Migration Required

> Apply `migrations/phase_136_provider_capability_registry.sql` in Supabase SQL editor.

## Test Results

42/42 contract tests passing ✅
