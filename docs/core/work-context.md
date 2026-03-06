# iHouse Core – Work Context

Current Phase
Phase 25 – OTA Modification Resolution Rules

Last Closed Phase
Phase 24 – OTA Modification Semantics


System State

The canonical event system is fully operational.

Key invariants:

- apply_envelope RPC remains the only authority allowed to mutate booking_state
- event_log is append-only
- booking_state is projection-only
- OTA payloads are normalized and validated before canonical envelope creation


Completed Phases

Phase 21
Defined canonical OTA ingestion boundary.

Phase 22
Implemented OTA adapter layer and normalization pipeline.

Phase 23
Introduced deterministic semantic classification and semantic validation
for OTA events before envelope creation.

Phase 24
Introduced explicit semantic recognition for OTA modification events.

The system now recognizes OTA modification events using the intermediate
semantic kind:

MODIFY

Modification events are allowed through semantic classification but must
be rejected deterministically at the adapter boundary when they cannot be
resolved safely from payload semantics.


Current Objective

Phase 25 defines deterministic resolution rules for OTA modification events.

Adapters must only resolve modification events if their canonical meaning
can be determined strictly from payload semantics.

If deterministic resolution is not possible, the event must be rejected
before canonical envelope creation.

This preserves the deterministic ingestion contract while enabling future
support for safe modification handling.
