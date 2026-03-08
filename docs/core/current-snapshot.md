# iHouse Core — Current Snapshot

## Current Phase
Phase 41 — DLQ Alerting Threshold

## Last Closed Phase
Phase 40 — DLQ Observability

## System Status

The deterministic event architecture remains fully operational.

`apply_envelope` remains the only authority allowed to mutate canonical booking state.

The DLQ layer (Phases 38-40) is now complete:
- rejected events preserved (`dead_letter.py`)
- replay available (`dlq_replay.py`)
- observability available (`dlq_inspector.py` + `ota_dlq_summary` view)

## Phase 40 Result

[Claude]

**Migration:** `ota_dlq_summary` view created in Supabase — groups `ota_dead_letter` rows by `event_type` + `rejection_code`, with `total`, `pending`, `replayed` counts.

**Module:** `src/adapters/ota/dlq_inspector.py`:
- `get_pending_count()` → int
- `get_replayed_count()` → int
- `get_rejection_breakdown()` → list[dict] from `ota_dlq_summary`

E2E verified: 3 pending rows, 1 replayed, breakdown visible by provider/rejection type.

## DLQ Layer Summary (Phases 38-40)

| Component | Where | What |
|-----------|-------|------|
| `ota_dead_letter` table | Supabase | append-only, RLS |
| `ota_dlq_summary` view | Supabase | read-only grouped summary |
| `dead_letter.py` | `src/adapters/ota/` | best-effort write on rejection |
| `dlq_replay.py` | `src/adapters/ota/` | safe, idempotent, manual replay |
| `dlq_inspector.py` | `src/adapters/ota/` | read-only inspection |

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

| Gap | Status | Priority |
|-----|--------|----------|
| DLQ Alerting Threshold | Phase 41 next | medium |
| External Event Ordering Buffer | deferred | high |
| booking_id Stability Across Provider Schema Changes | deferred | medium |
| Reservation Amendment (BOOKING_AMENDED) | blocked — discovery needed | low |
