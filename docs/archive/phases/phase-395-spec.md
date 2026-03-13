# Phase 395 — Property Onboarding QuickStart + Marketing Pages

**Status:** Closed  
**Date:** 2026-03-13  
**Category:** 🏗️ Product Feature / Public Surface

## Context

External agent session introduced property onboarding functionality and marketing pages outside the phase system. Phase 395 normalizes and formalizes these changes after security repair (hardcoded credentials removed, TypeScript errors fixed).

## What Was Implemented

### Database (4 migrations applied to Supabase)

1. `create_properties_and_channel_map` (20260313084640)
   - `properties` table: property registry with QuickStart fields (type, location, capacity, source)
   - `channel_map` table: onboarding channel URL mappings
   - RLS: tenant_isolation + service_role bypass
   - UNIQUE(tenant_id, property_id) on both tables

2. `allow_public_onboarding_inserts` (20260313093737)
   - anon INSERT with `WITH CHECK (tenant_id = 'public-onboard')`
   - anon SELECT with `USING (tenant_id = 'public-onboard')`

3. `add_property_deduplication_constraints` (20260313103720)
   - Partial unique index on `properties(tenant_id, source_url)` WHERE source_url IS NOT NULL
   - Unique index on `channel_map(tenant_id, property_id, provider)`

4. `property_lifecycle_redesign` (20260313105847)
   - Added `status` (pending/approved/archived/rejected), `approved_at/by`, `archived_at/by` to `properties`
   - Created `tenant_property_config` table for clean ID generation (DOM-001 pattern)
   - RLS on new table, default seed for `public-onboard` tenant

### Frontend — New Public Pages (7)

| Page | Lines | Purpose |
|------|:-----:|---------|
| `app/(public)/about/page.tsx` | 379 | About marketing page |
| `app/(public)/channels/page.tsx` | 426 | Channels marketing page |
| `app/(public)/inbox/page.tsx` | 351 | Inbox marketing page |
| `app/(public)/platform/page.tsx` | 475 | Platform marketing page |
| `app/(public)/pricing/page.tsx` | 452 | Pricing marketing page |
| `app/(public)/reviews/page.tsx` | 338 | Reviews marketing page |
| `app/(public)/onboard/connect/page.tsx` | 1,097 | Listing QuickStart wizard |

### Frontend — New API Routes (2)

| Route | Lines | Purpose |
|-------|:-----:|---------|
| `app/api/onboard/route.ts` | 196 | Property creation endpoint (Supabase direct) |
| `app/api/listing/extract/route.ts` | 273 | Playwright-based Airbnb URL scraper |

### Frontend — Modified Files (5)

| File | Change |
|------|--------|
| `middleware.ts` | Added 10 public route prefixes |
| `sitemap.ts` | Added 7 sitemap entries |
| `PublicNav.tsx` | Added marketing page nav links |
| `PublicFooter.tsx` | Expanded footer with new page links |

### Backend — Modified Files (1)

| File | Change |
|------|--------|
| `src/api/onboarding_router.py` | Added 11 optional QuickStart fields to POST /onboarding/start |

## Repairs Applied

1. ✅ Removed hardcoded Supabase credentials from `api/onboard/route.ts` → env vars
2. ✅ Fixed TypeScript type error in `onboard/connect/page.tsx` (added `status` to conflictProperty type)

## Verification

- `npx tsc --noEmit` → 0 errors ✅
- Backend pytest → same 9 pre-existing infra failures, no new regressions ✅
- RLS policies verified: INSERT enforced to `tenant_id = 'public-onboard'` via WITH CHECK ✅
- All new tables have RLS enabled ✅

## Notes

- `channel_map` (Phase 395) is distinct from `property_channel_map` (Phase 135). Different purposes: onboarding URL capture vs outbound sync mapping.
- `api/listing/extract/route.ts` requires Playwright dependency (dynamically imported).
- Properties are created with `status='pending'` — admin approval endpoints not yet built.
- Clean ID generation uses `tenant_property_config.id_prefix` + `next_seq` (e.g., DOM-001).

## Metrics After Phase 395

- **Frontend pages:** 35 (22 protected + 13 public)
- **DB tables:** 40 (RLS enabled on all)
- **DB migrations:** 35
- **Backend tests:** ~7,069 collected, 9 pre-existing infra failures
- **TypeScript:** 0 errors
