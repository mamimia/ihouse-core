# Phase 159 — Guest Profile Foundation

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** ~20 contract tests  
**Total after phase:** ~4140 passing

## Goal

Create the `guest_profile` table and `guest_profile_router.py` as an optional side-table for guest contact and pre-arrival data. Linked to `booking_id` but never in canonical state.

## Deliverables

### New Files
- `migrations/phase_159_guest_profile.sql` — `guest_profile` table: id UUID PK, tenant_id, booking_id (FK-like TEXT, not enforced constraint), guest_name, phone, email, arrival_time TEXT, special_notes TEXT, id_verified BOOLEAN, readiness_status TEXT, created_at, updated_at. RLS. Index on (tenant_id, booking_id).
- `src/api/guest_profile_router.py` — `GET /guests/{booking_id}` (404 if no profile), `POST /guests` (create or upsert by booking_id + tenant_id), `PATCH /guests/{booking_id}` (partial update)

### Modified Files
- `src/main.py` — guest_profile_router registered

### New Test Files
- `tests/test_guest_profile_contract.py` — ~20 contract tests

## Key Design Decisions
- `booking_id` is a soft reference — no FK constraint, so profile survives booking deletion (audit integrity)
- `readiness_status`: 'pending' | 'ready' | 'issue' — operational signal for operations dashboard
- Upsert on POST: if profile for booking_id already exists for tenant, overwrite (idempotent)
- RLS tenant isolation on all operations

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Guest profile is a side-table read model — zero canonical state impact ✅
