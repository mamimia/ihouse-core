# Phase 801 — Property Config & Channel Mapping

**Status:** Closed
**Prerequisite:** Phase 800 (Single-Tenant Live Activation + Auth Identity Fix)
**Date Closed:** 2026-03-15

## Goal

Configure actual properties for the staging tenant and link them to OTA channels. Add a composite endpoint that returns property metadata + channel mappings in a single call, reducing frontend roundtrips.

## Invariant

- `property_channel_map` is outbound config only — `apply_envelope` is never involved.
- Tenant isolation: all queries scoped by JWT `sub` claim.
- Read-only composite endpoint — no writes to any table.

## Design / Files

| File | Change |
|------|--------|
| `src/api/property_config_router.py` | NEW — composite `GET /admin/property-config` (list) + `GET /admin/property-config/{property_id}` (single) |
| `src/main.py` | MODIFIED — registered `property_config_router` |
| `tests/test_property_config_contract.py` | NEW — 15 contract tests |

## Data Seeded (Supabase Live)

### Properties (tenant_e2e_amended)

| property_id | display_name | timezone | currency | status |
|---|---|---|---|---|
| `phangan-villa-01` | Sunset Villa Koh Phangan | Asia/Bangkok | THB | approved |
| `samui-resort-02` | Ocean View Resort Samui | Asia/Bangkok | THB | approved |
| `chiangmai-house-03` | Mountain House Chiang Mai | Asia/Bangkok | THB | approved |

### Channel Mappings (7 total)

| property_id | provider | external_id | sync_mode |
|---|---|---|---|
| `phangan-villa-01` | bookingcom | `bcom_phangan01` | api_first |
| `phangan-villa-01` | airbnb | `abnb_phangan01` | ical_fallback |
| `phangan-villa-01` | agoda | `agoda_phangan01` | api_first |
| `samui-resort-02` | bookingcom | `bcom_samui02` | api_first |
| `samui-resort-02` | expedia | `exp_samui02` | api_first |
| `chiangmai-house-03` | airbnb | `abnb_cm03` | ical_fallback |
| `chiangmai-house-03` | agoda | `agoda_cm03` | api_first |

## Result

**15 new tests pass. 46 existing channel-map tests pass. 0 regressions.**
