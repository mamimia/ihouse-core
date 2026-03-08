# iHouse Core — Current Snapshot

## Current Phase
Phase 40 — TBD

## Last Closed Phase
Phase 39 — DLQ Controlled Replay

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

Rejected OTA events are preserved in `ota_dead_letter` and can now be replayed through `replay_dlq_row(row_id)` back through the canonical pipeline.

## Phase 39 Result

[Claude]

**Migration:** `replayed_at`, `replay_result`, `replay_trace_id` added to `ota_dead_letter`.

**Module:** `src/adapters/ota/dlq_replay.py` — `replay_dlq_row(row_id)`:
- reads specific DLQ row
- idempotency guard: already-applied rows return previous result, no re-processing
- new idempotency key per replay (`dlq-replay-{id}-{hex}`) — never reuses original key
- always routes through `apply_envelope` — never bypasses canonical gate
- writes outcome back: `replayed_at`, `replay_result`, `replay_trace_id`

E2E verified: BOOKING_CREATED → BOOKING_CANCELED_IN_DLQ → `replay_dlq_row` → `APPLIED` + idempotent second replay.

No automatic retry introduced. No canonical write path bypassed.

## DLQ Layer Summary (Phases 38-39)

| Component | Where |
|-----------|-------|
| `ota_dead_letter` table | Supabase — append-only, RLS |
| `dead_letter.py` | best-effort write on rejection |
| `dlq_replay.py` | safe, idempotent, manual replay |

## Canonical External OTA Events

- BOOKING_CREATED
- BOOKING_CANCELED

## Canonical Invariants

Event Store
- event_log is append-only
- events are immutable

State Model
- booking_state is projection-only
- booking_state is derived exclusively from events

Write Authority
- apply_envelope RPC is the only authority allowed to mutate booking state

Replay Safety
- duplicate envelopes must not create new events
- duplicate ingestion must remain idempotent

Business Identity
- booking_id = "{source}_{reservation_ref}" — deterministic and canonical
- business-level dedup enforced by apply_envelope at the DB gate

## Known Open Gaps (Deferred)

| Gap | Current Behavior | Priority |
|-----|-----------------|----------|
| Out-of-order events (CANCELED before CREATED) | Deterministic rejection → DLQ preserved → manual replay available | high |
| DLQ Observability & Alerting | Not implemented | medium |
| External Event Ordering Buffer | Not implemented | high |
| booking_id Stability Across Provider Schema Changes | Not implemented | medium |
