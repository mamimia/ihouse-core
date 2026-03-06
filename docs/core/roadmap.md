# iHouse Core – Roadmap


Completed

Phase 21  
External OTA ingestion boundary defined.

Phase 22  
OTA adapter layer introduced with normalization and validation.

Phase 23  
Semantic classification layer introduced for OTA events.

Phase 24  
OTA modification semantic recognition (MODIFY) introduced with
deterministic rejection of unresolved modification events.

Phase 25  
OTA modification resolution rules closed with deterministic
reject-by-default preserved.

Phase 26  
OTA payload contract verification completed across multiple providers.

Phase 27  
Multi-OTA adapter architecture introduced with a shared pipeline,
multi-provider registry, and provider extensibility proof through
Booking.com plus an Expedia scaffold adapter.


Upcoming


Phase 28  
OTA external surface decision.

Goal:
Decide whether the current single external OTA envelope kind
(`BOOKING_SYNC_INGEST`) remains sufficient for multi-provider scale,
or whether the canonical external surface must be split into more
explicit deterministic kinds.

Key question:
Should the OTA boundary continue to emit one canonical external
envelope kind with semantic differentiation inside payload fields,
or should CREATE and CANCEL outcomes be represented by more explicit
external canonical kinds?

Constraint:
No reconciliation layer may be introduced in this phase.
No booking_state lookup may be introduced in this phase.


Phase 29  
OTA ingestion replay harness.

Goal:
Create deterministic replay tools to simulate external OTA event
streams against the canonical ingestion pipeline.


Phase 30  
External integration test harness.

Goal:
End-to-end verification of OTA ingestion behavior across adapters,
including rejection scenarios and replay safety.


Phase 31  
Operational observability for OTA ingestion.

Goal:
Introduce structured logging, metrics, and ingestion visibility
for OTA adapters without modifying the deterministic event model.

## Future OTA Evolution — Amendment Handling

Status: Future improvement (not implemented)

Current system behavior intentionally supports only two deterministic OTA lifecycle outcomes:

- BOOKING_CREATED
- BOOKING_CANCELED

OTA modification events are currently classified as:

MODIFY → deterministic reject

This behavior is intentional and protects the canonical event model from ambiguous state mutation.

The system does not yet support reservation amendments.

---

### Why Amendments Are Not Implemented Yet

OTA providers frequently emit "modification" events representing partial reservation changes.

Examples:

- date change
- price change
- guest count change
- room change
- reservation correction
- OTA-side reconciliation

These events are problematic because they are often:

- non-deterministic
- partial
- emitted out of order
- emitted as snapshots instead of deltas
- dependent on external state

Allowing these events directly into the canonical event model would risk violating core invariants.

Therefore the current system design enforces:

MODIFY → deterministic reject

This ensures that canonical system truth is never derived from ambiguous OTA modification signals.

---

### Future Goal

Introduce deterministic amendment support without violating the core architectural invariants.

The system may eventually introduce a new canonical lifecycle event:

BOOKING_AMENDED

This event would represent a deterministic modification to an existing reservation.

However, amendments must only be introduced once the system can safely determine:

- what changed
- what the previous state was
- whether the change is valid
- whether events arrived in correct order
- whether the modification conflicts with existing bookings

---

### Requirements Before Amendment Support Can Be Introduced

The following architectural capabilities must exist before amendments are allowed:

1. Deterministic amendment classification

Adapters must be able to detect safe amendment scenarios such as:

- date extension
- date reduction
- guest count update

Ambiguous modifications must still be rejected.

2. Reservation identity stability

The system must be able to guarantee that an amendment references the same reservation identity.

3. State-safe amendment application

The core system must safely transition:

previous booking state → amended booking state

without violating:

- availability
- overlap rules
- historical event integrity

4. Out-of-order protection

OTA systems frequently emit events out of order.

The system must ensure amendments cannot corrupt booking state if events arrive late.

5. Projection safety

Booking projections must correctly rebuild amended reservations from event history.

---

### Potential Future Canonical Event

Example future event:

BOOKING_AMENDED

Payload example:

{
  "reservation_id": "...",
  "previous_dates": {...},
  "new_dates": {...},
  "amendment_reason": "date_change"
}

This event must remain deterministic and reconstructable from the event log.

---

### When Amendment Support Should Be Implemented

Amendment support should only be considered after:

- multiple OTA providers are live
- OTA payload behavior is well understood
- system projections are stable
- out-of-order handling strategy is defined

Until then the correct behavior remains:

MODIFY → deterministic reject