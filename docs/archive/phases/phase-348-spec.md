# Phase 348 — Webhook Ingestion Regression Suite

**Closed:** 2026-03-12
**Category:** 📡 Webhooks / Testing / Regression
**Test file:** `tests/test_webhook_regression_p348.py`

## Summary

Regression tests exercising all 14 OTA adapters (normalize + to_canonical_envelope),
LINE webhook endpoint, webhook event log service, and adapter registry edge cases.
Uses provider-correct payloads with exact field names (booking_ref, voucher_ref,
listing_id, hotel_id, hotel_code, activity_id, unit_id, etc.).

## Tests Added: 70

### Group A — Adapter normalize() Contract (28 tests)
- 14 providers × 2 tests (type check + required fields)

### Group B — Adapter to_canonical_envelope() Contract (28 tests)
- 14 providers × 2 tests (type check + required fields)

### Group C — LINE Webhook Regression (5 tests)
- PENDING→ACKNOWLEDGED, idempotent, terminal 409, 404, missing field 400

### Group D — Webhook Event Log (4 tests)
- log_webhook_event, stats, rejected events, clear

### Group E — Edge Cases + Registry (5 tests)
- Unknown provider, ctrip alias, provider name matching, interface check, tenant preservation

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 6,869 | 6,939 |
| Test files | 231 | 232 |
| New tests | — | 70 |
