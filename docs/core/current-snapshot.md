# iHouse Core — Current Snapshot

## Current Phase
Phase 37 — TBD

## Last Closed Phase
Phase 36 — Business Identity Canonicalization

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` through the canonical emitted business event contract.

Business identity is deterministic. Business dedup is enforced by `apply_envelope`.

## Phase 36 Result

[Claude]

Phase 36 verified and formally documented the canonical `booking_id` construction rule.

**Canonical booking_id rule:** `booking_id = "{source}_{reservation_ref}"`

This rule is applied consistently in `booking_created` and `booking_canceled` skills.

`apply_envelope` enforces business-level dedup in two layers:
1. By `booking_id` — direct uniqueness check
2. By composite `(tenant_id, source, reservation_ref, property_id)` — business identity check

E2E verified: a duplicate `BOOKING_CREATED` with a different `request_id` returns `ALREADY_EXISTS` — no new booking_state row is written.

No additional business-idempotency registry is required at this stage.

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
