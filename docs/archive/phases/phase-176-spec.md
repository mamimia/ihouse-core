# Phase 176 — Outbound Sync Auto-Trigger for BOOKING_CREATED

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** 26  
**Total after phase:** 4,627 passing

## Goal

Close the last gap in the outbound synchronization pipeline: `BOOKING_CREATED` events were never automatically triggering outbound sync to configured channels. `BOOKING_CANCELED` and `BOOKING_AMENDED` already had complete trigger paths (`cancel_sync_trigger.py`, `amend_sync_trigger.py`). This phase adds the equivalent path for `BOOKING_CREATED`.

## Deliverables

### New Files
- `src/services/outbound_created_sync.py` — Core trigger module. `fire_created_sync(booking_id, property_id, tenant_id, channels=None, registry=None)` fetches channel map + capability registry (with full DI for testing), calls `build_sync_plan` → `execute_sync_plan`, returns `List[CreatedSyncResult]`. Best-effort: all exceptions swallowed, never blocks ingest.
- `tests/test_outbound_auto_trigger_contract.py` — 26 contract tests across 5 groups (A: happy path, B: error handling, C: service wiring, D: regression guards for cancel/amend, E: result field contract).

### Modified Files
- `src/adapters/ota/service.py` — Added best-effort block in `ingest_provider_event_with_dlq`: after `BOOKING_CREATED` APPLIED, guards on non-empty `booking_id` + `property_id`, calls `fire_created_sync`.

## Key Design Decisions

- **Module-level imports** of `build_sync_plan` and `execute_sync_plan` in `outbound_created_sync.py` — essential for patchability in tests. Lazy (local) re-imports shadow module attributes and make mocking impossible.
- **Best-effort, non-blocking** — mirrors `cancel_sync_trigger.py` and `amend_sync_trigger.py` exactly.
- **DI params** (`channels`, `registry`) — allows full test isolation without hitting Supabase or setting env vars.
- **Guard on empty booking_id/property_id** — prevents meaningless outbound calls when event payload is incomplete.

## System State at Closing

| Layer | Status |
|-------|--------|
| Inbound OTA pipeline (11 providers) | ✅ Complete |
| Canonical state + financial layer | ✅ Complete |
| Outbound sync stack — BOOKING_CREATED | ✅ **Closed in this phase** |
| Outbound sync stack — BOOKING_CANCELED | ✅ Complete (prior) |
| Outbound sync stack — BOOKING_AMENDED | ✅ Complete (prior) |
| Task + SLA + notification foundation | ✅ Complete (SLA→dispatcher bridge pending) |
| Financial API (Rings 1–4) | ✅ Complete |
| Permissions + admin + audit | ✅ Complete |
| UI (6 screens deployed) | ✅ Partial — Worker Mobile + Auth Flow missing |

**Tests:** 4,627 passing. 2 pre-existing SQLite guard failures (unrelated, require live DB).

## Architecture Invariants Preserved
All 8 platform invariants verified intact at Phase 176 ✅
