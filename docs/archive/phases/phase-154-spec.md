# Phase 154 — API-first Cancellation Push

**Date closed:** 2026-03-10  
**Status:** ✅ Closed  
**Tests added:** ~25 contract tests  
**Total after phase:** ~4075 passing

## Goal

Extend all three API-first outbound adapters (Airbnb, Booking.com, Expedia/VRBO) with a `cancel()` method, enabling them to push booking cancellations to OTA channels via their APIs.

## Deliverables

### Modified Files
- `src/adapters/outbound/airbnb_adapter.py` — `cancel(external_id, booking_id, rate_limit)` method added; uses `_build_idempotency_key` with `cancel` suffix; dry-run on missing `AIRBNB_API_KEY`
- `src/adapters/outbound/bookingcom_adapter.py` — `cancel()` method added; same pattern; dry-run on missing `BOOKINGCOM_API_KEY`
- `src/adapters/outbound/expedia_vrbo_adapter.py` — `cancel()` method added; dry-run on missing `EXPEDIA_API_KEY`

### New Test Files
- `tests/test_sync_cancel_contract.py` — ~25 contract tests

## Key Design Decisions
- `cancel` suffix in idempotency key ensures cancel and send operations are distinct even for the same booking
- Dry-run path returns `status="dry_run"`, `strategy="api_first"` — same pattern as `send()`
- Rate limiting and retry via `_throttle` / `_retry_with_backoff` applied identically to `send()`
- 200 (not 204) expected from real OTA cancel endpoint — adapter normalizes to `AdapterResult`

## Architecture Invariants Preserved
- `apply_envelope` is the only write authority ✅
- Outbound adapters never mutate `booking_state` ✅
