# Phase 39 — DLQ Controlled Replay

## Status

Active

## Depends On

Phase 38 — Dead Letter Queue for Failed OTA Events

Phase 39 begins after Phase 38 confirmed that `ota_dead_letter` preserves rejected events but provides no replay mechanism.

## Objective

Implement a safe, manually-triggered, idempotent replay mechanism for events in `ota_dead_letter`.

Replay reads one DLQ row, re-runs the canonical skill, calls `apply_envelope`, and records the outcome back on the DLQ row.

## Design Constraints

Replay must:
- always go through the canonical skill → apply_envelope path
- never bypass apply_envelope
- never read booking_state directly
- be manually triggered per row
- be idempotent — safe to replay a row multiple times
- record the outcome (success or rejection reason) back on the DLQ row

## Implementation Plan

### Step 1 — Migration: add replay tracking columns

```sql
ALTER TABLE public.ota_dead_letter
  ADD COLUMN IF NOT EXISTS replayed_at    timestamptz,
  ADD COLUMN IF NOT EXISTS replay_result  text,
  ADD COLUMN IF NOT EXISTS replay_trace_id text;
```

### Step 2 — `src/adapters/ota/dlq_replay.py`

```python
def replay_dlq_row(row_id: int) -> dict
```

Flow:
1. Read row from `ota_dead_letter` by `id`
2. If already successfully replayed → return idempotent result
3. Determine skill from `event_type`
4. Re-run skill on `envelope_json['payload']`
5. Call `apply_envelope(envelope_json, emitted)`
6. Write `replayed_at`, `replay_result`, `replay_trace_id` back to the row
7. Return result dict

### Step 3 — Contract tests

- replay of a valid but previously-rejected row succeeds
- replay of a row that was already replayed is idempotent
- replay outcome is persisted on the DLQ row

## Completion Conditions

Phase 39 is complete when:
- `ota_dead_letter` has replay tracking columns
- `replay_dlq_row(row_id)` works and persists outcome
- replay is idempotent
- contract tests pass
- all existing tests still pass
