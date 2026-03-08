# iHouse Core — Current Snapshot

## Current Phase
Phase 38 — TBD

## Last Closed Phase
Phase 37 — External Event Ordering Protection Discovery

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` through the canonical emitted business event contract.

## Phase 37 Result

[Claude]

Phase 37 verified the current system behavior on out-of-order OTA event arrival.

**Verified behavior:**

- `BOOKING_CANCELED` before `BOOKING_CREATED` → `apply_envelope` raises `BOOKING_NOT_FOUND` (code `P0001`)
- This is a **deterministic rejection** — no silent data loss, no state corruption
- The rejected event is **lost** — there is no dead-letter store or retry queue in the active runtime path
- No buffering, retry, or ordering layer exists between the OTA adapter and `apply_envelope`

**Classification:** Known open gap, not a canonical invariant violation.

This remains deferred in `future-improvements.md` at priority **high** for a future implementation phase.

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
| Out-of-order events (CANCELED before CREATED) | Deterministic rejection — BOOKING_NOT_FOUND | high |
| Dead-letter store for failed events | Not implemented | medium |
| External event ordering buffer | Not implemented | high |
