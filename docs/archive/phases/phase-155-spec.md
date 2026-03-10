# Phase 155 — API-first Amendment Push

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** ~25 contract tests  
**Total after phase:** ~4100 passing

## Goal

Extend all three API-first outbound adapters with an `amend()` method so BOOKING_AMENDED events can be pushed to OTA channels via their APIs. New `amend_sync_trigger.py` service wired into `service.py`.

## Deliverables

### New Files
- `src/services/amend_sync_trigger.py` — builds sync plan for BOOKING_AMENDED events; calls `execute_sync_plan()` with `amend` action type

### Modified Files
- `src/adapters/outbound/airbnb_adapter.py` — `amend(external_id, booking_id, check_in, check_out, rate_limit)` method added; idempotency key with `amend` suffix
- `src/adapters/outbound/bookingcom_adapter.py` — `amend()` method added
- `src/adapters/outbound/expedia_vrbo_adapter.py` — `amend()` method added
- `src/services/service.py` — `amend_sync_trigger` wired in best-effort block after BOOKING_AMENDED APPLIED

### New Test Files
- `tests/test_sync_amend_contract.py` — ~25 contract tests

## Key Design Decisions
- `amend` suffix in idempotency key — distinct from `send` and `cancel` operations
- `check_in` / `check_out` passed to `amend()` — adapters include updated dates in OTA API call body
- Best-effort: amend sync failure never blocks the canonical BOOKING_AMENDED pipeline
- Dry-run when API key missing — identical to `send()` and `cancel()` pattern

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority ✅
- Amendment sync is best-effort and never mutates `booking_state` ✅
