# iHouse Core — Current Snapshot

## Current Phase
Phase 33 — OTA Retry Business Idempotency Discovery

## Last Closed Phase
Phase 32 — OTA Ingestion Contract Test Verification

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

External systems interact with iHouse Core through the OTA ingestion boundary and then the canonical core ingest path.

## Phase 32 Result

Phase 32 closed the executable verification loop for the OTA ingestion runtime contract without changing canonical business semantics.

Phase 32 verified the live runtime handoff as:

ingest_provider_event  
→ process_ota_event  
→ canonical envelope  
→ IngestAPI.append_event  
→ CoreExecutor.execute  
→ apply_envelope

Phase 32 completed the following:

- added direct tests for thin OTA service entry
- added direct tests for ordered shared OTA pipeline responsibilities
- added direct tests for core ingest rejection of missing executor wiring
- aligned replay verification to the same public ingest contract
- verified no tested OTA runtime path bypasses core ingest or CoreExecutor
- reran relevant smoke and invariant checks successfully

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

## Phase 33 Focus

Phase 33 focuses on OTA retry business idempotency discovery.

This phase originally existed to determine whether OTA-originated duplicate business events can arrive with different transport identifiers and whether the current system already protects against that safely.

Discovery evidence gathered in this phase shows a more precise active concern:

- the canonical Supabase apply contract already contains business-level protection for BOOKING_CREATED when canonical emitted business events reach `apply_envelope`
- the active OTA runtime path currently appears misaligned with that canonical emitted event contract
- the main verified discovery is therefore runtime mapping and routing alignment risk between OTA envelopes, executor skill routing, emitted business events, and the Supabase apply contract

This phase remains a discovery, evidence gathering, and minimal verification phase only.

It must not redesign the architecture.

It must not reopen closed semantic decisions.

## Active Discovery Position

The current strongest evidence is:

- OTA adapters build transport-facing envelopes using provider-oriented fields such as `provider`, `reservation_id`, `property_id`, and transport idempotency derived from `external_event_id`
- CoreExecutor forwards the original envelope plus emitted events to `apply_envelope`
- `apply_envelope` performs canonical business handling from emitted events, not from the raw OTA envelope alone
- the active runtime skill routing currently maps `BOOKING_CREATED` to a noop skill, which does not emit the canonical business event shape required by the Supabase apply contract
- therefore the currently verified risk is not a proven failure of canonical business dedup itself, but a likely mapping and routing gap in the active OTA runtime path

## Current Objective

Determine whether the active OTA runtime path actually reaches the canonical emitted business event contract expected by `apply_envelope`, or whether a routing and mapping gap currently prevents canonical business identity enforcement from being applied as intended.

This objective remains bounded by the same Phase 33 restrictions:

- no reconciliation
- no amendment handling
- no booking_state reads inside adapters
- no direct apply_envelope calls from OTA code
- no alternative write paths
- no new canonical event kinds
- no reopening closed phase decisions

## Next Minimal Step

Document the verified discovery precisely in the active docs, then define the smallest safe future hardening direction only if the active OTA runtime path is confirmed to remain misaligned with the canonical emitted business event contract.
