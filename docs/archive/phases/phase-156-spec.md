# Phase 156 — Property Metadata Table

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** ~20 contract tests  
**Total after phase:** ~4120 passing

## Goal

Create a canonical store for property display information — name, address, type, bedroom count, timezone. Required by all UI surfaces that need to show "which property" in context.

## Deliverables

### New Files
- `migrations/phase_156_properties.sql` — `properties` table: id (TEXT PK = property_id), tenant_id, name, address, property_type, bedrooms, timezone, active BOOLEAN, created_at, updated_at. RLS. 2 indexes (tenant_id, tenant+active).
- `src/api/properties_router.py` — `GET /properties` (list, tenant-scoped, active filter), `POST /properties` (create), `PATCH /properties/{id}` (partial update), `DELETE /properties/{id}` (soft-delete via active=false)

### Modified Files
- `src/main.py` — properties_router registered

### New Test Files
- `tests/test_properties_router_contract.py` — ~20 contract tests

## Key Design Decisions
- `property_id` is the PK — same value used in `booking_state`, `outbound_sync_log`, `tasks`; no join needed
- `timezone` column added here (same as `property_channel_map.timezone` from Phase 150) — canonical source of truth
- Soft-delete: properties are set `active=false`, never physically deleted (preserves audit integrity)
- RLS enforces tenant isolation: `tenant_id = current_setting('app.tenant_id')`

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Properties table is a metadata side-table — zero canonical state impact ✅
