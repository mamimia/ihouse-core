# iHouse Core — Current Snapshot

## Current Phase
Phase 39 — TBD

## Last Closed Phase
Phase 38 — Dead Letter Queue for Failed OTA Events

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

OTA events rejected by `apply_envelope` are now preserved in `ota_dead_letter` instead of being silently lost.

## Phase 38 Result

[Claude]

Phase 38 implemented a minimal, append-only Dead Letter Queue.

**Supabase table:** `ota_dead_letter` — append-only, RLS enabled for service_role  
**Module:** `src/adapters/ota/dead_letter.py` — best-effort, non-blocking, swallows errors  
**Service:** `ingest_provider_event_with_dlq` added to `service.py`, original wrapper preserved

E2E verified: `BOOKING_CANCELED` before `BOOKING_CREATED` → `apply_envelope` raises `BOOKING_NOT_FOUND` → DLQ row written with `rejection_code: P0001`

The DLQ is:
- append-only
- non-blocking (never raises)
- never bypasses `apply_envelope`
- never mutates canonical state
- observable via SQL query on `ota_dead_letter`

No canonical business semantics changed.
No alternative write path was introduced.
MODIFY remains deterministic reject-by-default.

## Canonical External OTA Events

The canonical OTA lifecycle events remain:

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
| Out-of-order events (CANCELED before CREATED) | Deterministic rejection → DLQ preserved | high |
| Out-of-order replay / retry from DLQ | Not implemented | high |
| External event ordering buffer | Not implemented | high |
