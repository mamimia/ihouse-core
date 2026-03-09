# Phase 79 — Idempotency Monitoring

## Status: CLOSED

## Objective

Add `src/adapters/ota/idempotency_monitor.py` — a pure read-only module that collects idempotency health metrics from existing Supabase tables. No new schema.

## Design

### Schema Discovery

- `event_log` does NOT have `idempotency_key` or `provider` columns  
- Idempotency is tracked via `event_id` + `ON CONFLICT` in `apply_envelope`  
- Monitoring signals available via `ota_dead_letter` (rejection_code) and `ota_ordering_buffer` (status)

### `IDEMPOTENCY_REJECTION_CODES` constant

```
frozenset: ALREADY_APPLIED, ALREADY_EXISTS, ALREADY_EXISTS_BUSINESS, DUPLICATE
```

### `IdempotencyReport` (frozen dataclass)

| Field | Source |
|---|---|
| `total_dlq_rows` | all rows in `ota_dead_letter` |
| `pending_dlq_rows` | rows where replay_result not in APPLIED_STATUSES |
| `already_applied_count` | rows where replay_result in APPLIED_STATUSES |
| `idempotency_rejection_count` | rows where rejection_code in IDEMPOTENCY_REJECTION_CODES |
| `ordering_buffer_depth` | `ota_ordering_buffer` rows with status='waiting' |
| `checked_at` | UTC ISO timestamp |

### Rules
- Never writes to any table
- Never raises on missing data (empty table = safe zero defaults)
- `collect_idempotency_report(client=None)` — client injectable for testing

## Files Added

- `src/adapters/ota/idempotency_monitor.py`
- `tests/test_idempotency_monitor_contract.py`

## Result

**633 passed, 2 skipped** (pre-existing SQLite skips)  
35 contract tests (Groups A–F: structure, DLQ classification, rejection codes, ordering buffer, safe defaults, constants).  
No Supabase schema changes. No new migrations.
