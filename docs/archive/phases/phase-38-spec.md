# Phase 38 — Dead Letter Queue for Failed OTA Events

## Status

Active

## Depends On

Phase 37 — External Event Ordering Protection Discovery

Phase 38 begins after Phase 37 confirmed that rejected OTA events are currently lost with no preservation mechanism.

## Objective

Implement a minimal, append-only Dead Letter Queue (DLQ) so that OTA events rejected by `apply_envelope` are preserved for investigation and future replay — not silently lost.

## What This Phase Is NOT

- Not a retry system
- Not a reconciliation layer
- Not a new canonical write path
- Not amendment handling

## Design Constraints

The DLQ must:
- be append-only
- not bypass `apply_envelope`
- not read `booking_state`
- not mutate canonical state
- not automatically requeue or retry

## Implementation Plan

### 1. Supabase Table: `ota_dead_letter`

```sql
CREATE TABLE public.ota_dead_letter (
  id              bigserial PRIMARY KEY,
  received_at     timestamptz NOT NULL DEFAULT now(),
  provider        text NOT NULL,
  event_type      text NOT NULL,
  rejection_code  text NOT NULL,
  rejection_msg   text,
  envelope_json   jsonb NOT NULL,
  emitted_json    jsonb,
  trace_id        text
);
```

### 2. OTA Service Layer: capture rejections

In `src/adapters/ota/service.py`, after `IngestAPI.append_event`:
- if `apply_envelope` raises an exception or returns a non-APPLIED status → write to DLQ
- DLQ write must be best-effort (does not block the OTA response)

### 3. Verification

- E2E test: send BOOKING_CANCELED before BOOKING_CREATED → verify row appears in `ota_dead_letter`
- Regression: normal BOOKING_CREATED still results in APPLIED, no DLQ row

## Completion Conditions

Phase 38 is complete when:
- `ota_dead_letter` table exists in Supabase
- rejected OTA events are preserved in `ota_dead_letter` instead of being lost
- successful OTA events do not create DLQ rows
- all existing tests still pass
