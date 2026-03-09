# Phase 79 — Idempotency Monitoring

**Status:** Closed
**Prerequisite:** Phase 78 — OTA Schema Normalization (Dates + Price)
**Date Closed:** 2026-03-09

## Goal

Add a pure read-only idempotency health monitoring module. The system had no structured way to observe duplicate event signals, DLQ idempotency rejections, or ordering buffer depth. This phase provides a single `collect_idempotency_report()` function that returns a frozen snapshot of these metrics, injectable for testing without a live DB.

## Invariant

- `idempotency_monitor.py` never writes to any table
- Missing or empty tables yield zero-value metrics — never raises
- `apply_envelope` remains the sole write authority

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/idempotency_monitor.py` | NEW — `IDEMPOTENCY_REJECTION_CODES`, `IdempotencyReport`, `collect_idempotency_report()` |
| `tests/test_idempotency_monitor_contract.py` | NEW — 35 contract tests (Groups A–F) |

### `IdempotencyReport` fields

| Field | Source |
|---|---|
| `total_dlq_rows` | all rows in `ota_dead_letter` |
| `pending_dlq_rows` | replay_result not in APPLIED_STATUSES |
| `already_applied_count` | replay_result in APPLIED_STATUSES |
| `idempotency_rejection_count` | rejection_code in IDEMPOTENCY_REJECTION_CODES |
| `ordering_buffer_depth` | `ota_ordering_buffer` rows with status='waiting' |
| `checked_at` | UTC ISO timestamp |

## Result

**633 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
