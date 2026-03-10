# Phase 173 — IPI: Proactive Availability Broadcasting

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 35 contract tests  
**Total after phase:** 4503 passing

## Goal

Implement Intelligent Proactive Integration (IPI) — a property-level broadcaster that proactively pushes availability to all channels when a property is onboarded or a new channel is added. Also closed the Phase 171 audit debt by wiring `write_audit_event()` into the grant/revoke (Phase 167) and PATCH provider (Phase 169) endpoints.

## Deliverables

### New Files
- `src/services/outbound_availability_broadcaster.py`:
  - `BroadcastMode` enum: `PROPERTY_ONBOARDED`, `CHANNEL_ADDED`
  - `BookingBroadcastResult`, `BroadcastReport` dataclasses
  - `_fetch_channels()`, `_fetch_registry()`, `_fetch_active_booking_ids()` — injectable DB helpers (best-effort, never raise)
  - `broadcast_availability(db, *, tenant_id, property_id, mode, source_provider, target_provider, ...)` — reads `property_channel_map` + `provider_capability_registry` + `booking_state`; builds sync plan per booking via `build_sync_plan()`; executes via `execute_sync_plan()`; per-booking fail-isolated; never raises
  - `serialise_broadcast_report()` — JSON-serialisable output for API response
- `src/api/broadcaster_router.py` — `POST /admin/broadcast/availability`: validates mode + required fields; delegates to broadcaster; always returns 200 with `BroadcastReport`
- `tests/test_availability_broadcaster_contract.py` — 35 contract tests (Groups A–K)

### Modified Files
- `src/main.py` — broadcaster_router registered
- `src/api/permissions_router.py` — `write_audit_event()` wired into grant and revoke (Phase 171 debt)
- `src/api/capability_registry_router.py` — `write_audit_event()` wired into PATCH provider (Phase 171 debt)

## Key Design Decisions
- Broadcaster is a thin orchestration layer — delegates all sync logic to existing Phase 137 + 138 functions
- Per-booking fail-isolation: one booking's sync failure never blocks others
- `CHANNEL_ADDED` mode: only push to the newly added target_provider (not all channels)
- `PROPERTY_ONBOARDED` mode: push all active bookings to all configured channels
- Audit events written for broadcaster calls via `write_audit_event()` pattern

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority to `booking_state` ✅
- Broadcaster is read + orchestration only — never writes to `booking_state` ✅
- All sync results flow through `execute_sync_plan()` and `_persist()` — audit trail maintained ✅
