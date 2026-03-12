# Phase 335 — Outbound OTA Adapter Integration Tests

**Status:** Closed
**Prerequisite:** Phase 334 (Booking Dates + iCal Push Adapter Integration Tests)
**Date Closed:** 2026-03-12

## Goal

Write first-ever integration tests for the 3 remaining zero-test outbound OTA adapters: `airbnb_adapter.py`, `bookingcom_adapter.py`, `expedia_vrbo_adapter.py`. These modules build OTA-specific push payloads with injectable HTTP clients and handle send/cancel/amend lifecycle operations.

## Invariant

All outbound adapters must return `dry_run` status when API keys are absent. Adapters must never raise exceptions — all failures return `AdapterResult(status="failed")`.

## Design / Files

| File | Change |
|------|--------|
| `tests/test_outbound_ota_adapter_integration.py` | NEW — 38 integration tests across 8 groups |

## Result

**38 tests pass, 0 skipped, 0 failed.** (0.25s)

Coverage: AirbnbAdapter (10 tests), BookingComAdapter (9 tests), ExpediaVrboAdapter (10 tests), Idempotency Key (5 tests), Shared Infrastructure (4 tests).
