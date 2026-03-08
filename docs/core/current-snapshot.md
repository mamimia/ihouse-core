# iHouse Core — Current Snapshot

## Current Phase
Phase 34 — OTA Canonical Event Emission Alignment

## Last Closed Phase
Phase 33 — OTA Retry Business Idempotency Discovery

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

External systems interact with iHouse Core through the OTA ingestion boundary and then the canonical core ingest path.

## Phase 33 Result

Phase 33 closed the discovery loop around OTA retry business idempotency without changing canonical business semantics.

Phase 33 verified that the live runtime handoff remains:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.append_event  
→ CoreExecutor.execute  
→ apply_envelope

Phase 33 established the following:

- transport idempotency in the OTA adapter path is currently derived from provider `external_event_id`
- canonical Supabase business handling already exists for canonical emitted business events
- `apply_envelope` performs canonical business handling from emitted events, not from the raw OTA envelope alone
- the active OTA runtime path currently appears misaligned with the canonical emitted business event contract expected by `apply_envelope`
- the strongest verified risk is runtime mapping and routing misalignment, not a proven intrinsic failure of canonical Supabase business dedup logic

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

## Phase 34 Focus

Phase 34 focuses on OTA canonical event emission alignment.

This phase exists to verify and align the active OTA runtime path so that OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED` reach `apply_envelope` through the canonical emitted business event contract expected by Supabase.

This phase is narrow by design.

It must not redesign the architecture.

It must not introduce reconciliation logic, amendment handling, adapter-side state mutation, booking_state reads inside adapters, direct OTA calls to `apply_envelope`, or alternative write paths.

## Current Objective

Determine exactly where the active OTA runtime path fails to emit the canonical business event shape expected by `apply_envelope`, and define the smallest safe alignment work required to restore canonical enforcement.

## Next Minimal Step

Inspect active skill routing and emitted event construction for OTA-originated `BOOKING_CREATED` and `BOOKING_CANCELED`, then define the minimum alignment change required without reopening any closed semantic decision.
