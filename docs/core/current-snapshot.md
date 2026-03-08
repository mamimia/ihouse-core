# iHouse Core — Current Snapshot

## Current Phase
Phase 35 — OTA Canonical Emitted Event Alignment Implementation

## Last Closed Phase
Phase 34 — OTA Canonical Event Emission Alignment

## System Status

The deterministic event architecture remains fully operational.

The canonical database gate (`apply_envelope`) remains the only authority allowed to mutate booking state.

External systems interact with iHouse Core through the OTA ingestion boundary and then the canonical core ingest path.

## Phase 34 Result

[Claude]

Phase 34 proved a routing and emitted-event alignment gap in the active OTA runtime path.

Phase 34 verified that `BOOKING_CREATED` currently routes to a noop skill (zero events) and `BOOKING_CANCELED` has no active route.

Phase 34 established that the active OTA runtime path is misaligned with the canonical emitted business event contract expected by `apply_envelope`.

No canonical business semantics changed.
No architecture redesign was justified.
MODIFY remains deterministic reject-by-default.

## Canonical External OTA Events

The canonical OTA lifecycle events remain:

- BOOKING_CREATED
- BOOKING_CANCELED
