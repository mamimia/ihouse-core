# iHouse Core – Phase Timeline (Append-Only Chronicle)

## Constitutional Rule

This file is the authoritative chronological archive of iHouse Core evolution.

Rules:

1. This document is strictly append-only.
2. No historical section may ever be edited or deleted.
3. Corrections must be appended as new entries.
4. Every Phase closure MUST append a new section here.
5. Phase closure is not complete without updating this file.

---

## Phase 1 – Event Foundation
Immutable append-only events table established.
Envelope discipline introduced.
State declared derived.
No silent overrides allowed.
Company isolation enforced.

## Phase 2 – Deterministic Projection & Rebuild
Projection tables introduced.
Deterministic rebuild implemented.
Replay validated identical.
Rebuild deletes projections only, never events.

## Phase 3 – Idempotency & Integrity Stabilization
Database-level idempotency enforced.
UNIQUE constraint on events.event_id.
INSERT OR IGNORE semantics introduced.

## Phase 4 – Deterministic Rebuild Contract
Fingerprint validation added.
Smoke suite integration.
Events table declared immutable during rebuild.

## Phase 5 – Version Discipline
Replay-driven version inflation prevented.
Forward/backward compatibility discipline locked.
Version stability guaranteed under replay.

## Phase 6 – Outbox & Concurrency Hardening
Outbox table introduced.
Claim + lease multi-worker safety.
Double execution prevention enforced.

## Phase 7 – Infrastructure Hardening
WAL enforced.
foreign_keys enforced.
busy_timeout enforced.
Deterministic rebuild validated twice.
verify_phase7.sh introduced.

## Phase 8 – Ingest & Query API Surface
FastAPI introduced.
POST /events ingest defined.
Query surface formalized.

## Phase 9 – HTTP Hardening
API key enforcement.
Structured logging.
No stack leakage policy.

## Phase 10 – Skill Runner Hardening
Timeout enforcement.
Subprocess isolation stabilized.
kind_registry externalized.
Permanent rule: Never run pytest directly.

## Phase 11 – Single Source of Truth Routing
Kind→Skill mapping moved into Core.
Python default mapping removed.

## Phase 12 – Controlled Domain Refactor Preparation
Domain audit completed.
Skill classification defined.
Inward migration plan prepared.

## Phase 13A – Minimal Event Log Activation
Append-only event_log formalized.
Atomic envelope transaction defined.

## Phase 13B – Idempotent Commit Semantics
Commit only when apply_status == APPLIED.
booking_state.last_envelope_id introduced.
Replay must not increment version.

## Phase 13C – Supabase Operational Introduction
Supabase public.event_log created.
Supabase public.booking_state created.
Cloud persistence validated.
Composition root unified.
Explicit ports introduced.
Canonical runner defined.

## Phase 14 – StateStore Canonicalization
Single deterministic commit path enforced.
Replay never commits.
Hidden state writes eliminated.
Agent sidecar disabled.

## Phase 15 – Execution Surface Elimination
FastAPI sole execution entrypoint.
Parallel execution removed.
CoreExecutor declared single authority.

## Phase 16 – Canonical Domain Migration
16A – Canonical Schema Lock
16B – Deterministic Core Alignment
16C – Hard Idempotency Gate
Financial-grade atomic idempotency enforced.

## Phase 17A – Operational Runner & Governance Hardening
Canonical run_api.sh
Dev smoke scripts
CI enforcement rules
English-only repo policy
Secret-based API key
CI HTTP smoke validation

## Phase 17B – Canonical Governance Completion 
Finalize documentation alignment.
Treat user self-booking as canonical external event source.
Tighten operational invariants.

## Phase 17B – Canonical Governance Completion (Closed)
apply_envelope validated as single atomic write authority.
ALREADY_APPLIED replay validated with zero duplicate state mutation.
STATE_UPSERT formalized as DB-generated internal event.
booking_state last_envelope_id invariant validated.
Unique constraints and foreign keys verified live.
End-to-end determinism revalidated.
User self-booking confirmed as canonical external event source.

## Phase 17C – Overlap Rules, Business Dedup, Read Model Inquiry (Open)
Introduce overlap invariants.
Introduce business dedup keys.
Introduce stable read model inquiry API.

## Phase 17C — Overlap Rules, Business Dedup, Read Model Inquiry (Closed)
Completed:
- booking_state.check_in and booking_state.check_out added (date).
- Overlap gate enforced on BOOKING_CREATED using half-open range [check_in, check_out).
- Business identity dedup enforced for BOOKING_CREATED on (tenant_id, source, reservation_ref, property_id).
- Read model inquiry functions added:
  - read_booking_by_id(booking_id)
  - read_booking_by_business_key(tenant_id, source, reservation_ref, property_id)

Outcome:
- Deterministic, forward-only booking creation gate with overlap prevention and stable identity dedup.
- Read model inquiry is DB-backed and consistent.

## Phase 18 – Cancellation-aware Overlap (Closed)
Introduce cancellation-aware availability semantics and status-based booking lifecycle.

Canonical availability predicate:
- A booking is considered active for overlap checks iff status IS DISTINCT FROM 'canceled'.
- This intentionally treats NULL as active for legacy rows (forward-only, no backfill).

Forward-only write rules:
- On BOOKING_CREATED: always write status = 'active' for new rows.
- On BOOKING_CANCELED: set status = 'canceled' and bump version under row lock; update last_event_id and last_envelope_id.

Completed:
- booking_state.status column introduced.
- BOOKING_CANCELED branch implemented inside apply_envelope.
- Cancellation updates booking_state under row lock.
- Overlap gate modified to ignore canceled bookings using the canonical predicate.
- Canceling a booking allows a new overlapping booking to be created afterward.

Outcome:
- Cancellation removes bookings from availability checks without deleting historical data.
- Legacy rows with NULL status remain valid and are treated as active.
- Availability remains deterministic using half-open ranges [check_in, check_out).
- Booking lifecycle transitions remain forward-only and replay safe.

## Phase 19 – Event Version Discipline + DB Gate Validation (Closed)

Completed:
- Introduced DB gate validation for emitted events before enum cast.
- Enforced external allowlist discipline via registry.
- Transitional policy:
  - Missing event_version defaults to 1 only for allowlisted external kinds.
  - Missing event_version for non external kinds rejects with EVENT_VERSION_REQUIRED.
- Deterministic rejection codes locked:
  - UNKNOWN_EVENT_KIND
  - UNSUPPORTED_EVENT_VERSION
  - INVALID_PAYLOAD
  - EVENT_VERSION_REQUIRED
  - ALREADY_APPLIED

Tests:
- T3.1 missing_version (external allowlisted) => APPLIED
- T3.2 unsupported_version => UNSUPPORTED_EVENT_VERSION
- T3.3 unknown_kind => UNKNOWN_EVENT_KIND

Outcome:
- apply_envelope behaves as a deterministic protocol validator.
- Unknown kinds are rejected deterministically, not via enum cast failure.
- Legacy external producers remain compatible under Transitional policy.


## Phase 20 — Envelope Event Identity Hardening + Replay Safety (Closed)

- Canonical write gate reaffirmed: apply_envelope is the single atomic write authority.
- Projection discipline locked: booking_state is a read model; STATE_UPSERT is internal only.
- Replay safety verified: duplicate envelope replays do not create new events and do not mutate booking_state.
- Evidence recorded: Supabase function definitions exported to artifacts/supabase/Functions.sql.
- Legacy compatibility policy: NULL status tolerated and treated as active for availability; future backfill deferred.


## Future Improvements (Deferred Architecture Work)

### Event Time vs System Time Separation

Future improvement for distributed ingestion sources (OTA channels — Online Travel Agencies such as Booking.com, Airbnb, Expedia).

Introduce explicit separation between:

- occurred_at → the time when the business event actually happened in the external system
- recorded_at → the time when the event entered the canonical system ledger

Rationale:
External systems may deliver delayed or out-of-order events.
Separating business event time from system ingestion time preserves auditability,
supports correct replay behavior, and improves debugging of distributed integrations.

Status:
Deferred for a future phase.

Note:
When implemented, event_log should store both timestamps and the system should
use recorded_at for ordering guarantees while preserving occurred_at for business history.


### Dead Letter Queue for External Event Failures

Future improvement for handling invalid or failed external events.

Context:
When integrating external systems (OTA — Online Travel Agencies such as Booking.com, Airbnb, Expedia), the system may receive events that cannot be applied due to validation errors or missing state.

Instead of losing these events, the system should store them in a dedicated table.

Proposed mechanism:
dead_letter_events table that records:

- envelope_id
- event_type
- payload_json
- failure_reason
- recorded_at

Purpose:
- preserve failed events for investigation
- allow manual correction and replay
- maintain auditability of external integrations

Status:
Deferred to a future phase once OTA integrations are introduced.


## Future Improvements — Architecture Backlog

The following improvements are intentionally deferred to later phases.
They represent common SaaS architecture patterns but are not required
for the current system maturity.

### Event Time vs System Time
Separate business event time from ingestion time.

occurred_at  → time the event happened in the external system  
recorded_at  → time the event entered the canonical ledger

This becomes important when ingesting delayed OTA events.

---

### Dead Letter Queue
Introduce a table for failed external events.

dead_letter_events

Fields:

- envelope_id
- payload_json
- failure_reason
- recorded_at

Purpose:
Preserve invalid events for inspection and manual replay.

---

### Event Ordering Protection
External integrations may send events out of order.

Future system should detect and handle:

- out-of-order events
- missing events
- delayed events

---

### OTA Rate Limiting
Introduce rate limiting per tenant to protect the ingestion API.

Example:
events per tenant per minute.

---

### Idempotency Monitoring
Add metrics and monitoring for duplicate envelope detection.

Purpose:
detect integration bugs and retry storms.

---

### Multi Projection Support
Future projections beyond booking_state.

Examples:

- availability_projection
- revenue_projection
- analytics_projection

---

### Replay Snapshot Optimization
When the event log becomes large, introduce snapshots to speed up rebuild.

---

### External Event Signature Validation
Support webhook signature validation for OTA integrations.

Example mechanisms:

- HMAC signatures
- API key verification


## Future Improvements — OTA Integration Learnings

### OTA Out-of-Order Event Handling

External booking channels may deliver events out of order.

Example:
reservation.modified may arrive before reservation.created.

Future versions of the system may introduce a pending event buffer
or reconciliation mechanism to safely handle out-of-order events.

---

### OTA Retry Idempotency

External systems frequently retry the same webhook multiple times.

The ingestion layer must tolerate repeated events without mutating
the canonical ledger more than once.

---

### Channel Semantic Normalization

Different OTA channels use different event semantics.

Future work may introduce a dedicated normalization layer
for channel-specific payload mapping.

---

### Reservation Identity Normalization

External reservation identifiers are not always stable or uniform.

Future phases may introduce identity normalization
for external reservation references.

---

### Event Ordering Strategy

OTA events may contain business timestamps that differ from
system ingestion time.

Future improvements may formalize the separation between:

occurred_at (business event time)
recorded_at (system ingestion time).


## Phase 19 – Event Version Discipline + DB Gate Validation (Closed)

Outcome:
- External event_version discipline enforced by DB gate validation.
- Transitional missing-version policy locked to external allowlist (default v1).
- Deterministic rejection codes returned for invalid kinds/versions/payloads.
- Replay safety preserved: ALREADY_APPLIED must not mutate booking_state.

## Phase 20 — Envelope Event Identity Hardening + Replay Safety (Closed)

Completed:
- Confirmed apply_envelope RPC is the single write gate into event_log.
- Confirmed booking_state is projection-only and materialized via DB-generated STATE_UPSERT.
- Confirmed duplicate envelope replay inserts no new events and does not mutate booking_state.
- Supabase truth pack captured under artifacts/supabase/ for reference.

Operational notes:
- Legacy booking_state rows may have NULL business fields and/or legacy state_json shapes; forward-only tolerance remains.

## Phase 21 — External Ingestion Boundary Definition (Closed)

Goal:
Define the canonical boundary for external OTA ingestion without violating the canonical write gate.

Decisions:
- External systems never write directly to event_log or booking_state.
- All external events must pass through an ingestion adapter that emits canonical envelopes.
- The adapter performs normalization, validation, and dedup before calling apply_envelope.

Canonical pipeline:
External Source
→ Ingestion API
→ Normalization Layer
→ Validation Layer
→ apply_envelope RPC
→ event_log
→ projection (booking_state)

Security and integrity rules:
- Authentication required (JWT or equivalent).
- Idempotency enforced via envelope_id and business dedup key.
- External event kinds must be allowlisted.
- Unsupported OTA events are rejected rather than approximated.

Supported external kinds for Phase 21:
- BOOKING_CREATED
- BOOKING_CANCELED

Outcome:
The external boundary is defined without introducing a second write path, preserving replay safety and canonical event discipline.

---

## Future Improvements — OTA Integration Learnings

### OTA Out-of-Order Event Handling

External booking channels may deliver events out of order.

Example:
reservation.modified may arrive before reservation.created.

Future versions of the system may introduce a pending event buffer
or reconciliation mechanism to safely handle out-of-order events.

### Business Identity Enforcement

Current business identity:

tenant_id + source + reservation_ref + property_id

Future improvements may enforce stricter constraints and unique indexes
to guarantee deterministic booking identity across retries and OTA updates.

### Business Idempotency Layer

Envelope idempotency protects against transport retries.

Future versions may introduce a dedicated business idempotency registry
to protect against duplicate external events that carry different envelope_ids.

### OTA Schema Normalization

External channels often use different semantics for fields such as:

timezone  
currency  
guest counts  
reservation modifications

Future phases may introduce channel-specific normalization modules
to guarantee canonical event payload consistency.

### External Event Ordering Guards

Future versions may introduce tolerant state machines or buffering strategies
to safely process external events that arrive out of order.

### OTA Integration Hardening

Future phases may add:

rate limiting  
webhook replay protection  
audit logging  
channel-specific authentication policies


## Phase 22 — OTA Ingestion Boundary (Closed)

Goal:
Introduce a strict ingestion boundary between external booking systems
and the canonical event kernel.

Completed:

- Implemented adapter layer for external channel integrations.
- Introduced normalization pipeline converting external payloads into canonical events.
- Implemented validation pipeline prior to canonical envelope submission.
- Ensured idempotency propagation from external request IDs.
- Integrated adapter service with canonical ingest API.

Canonical ingestion pipeline:

External Channel
→ Adapter Layer
→ Normalized Event
→ Validation
→ Canonical Envelope
→ apply_envelope
→ event_log

Outcome:

External systems are now isolated from the internal event model.

The deterministic event kernel remains protected while enabling
future integrations with OTA channels, channel managers,
admin tools, and manual booking systems.

## Phase 23 — External Event Semantics Hardening (Closed)

Implemented deterministic semantic classification for OTA events before
canonical envelope creation.

New component:
src/adapters/ota/semantics.py

Pipeline:

normalize
→ validate_normalized_event
→ classify_normalized_event
→ validate_classified_event
→ to_canonical_envelope
→ validate_canonical_envelope
→ append_event

Result:

OTA provider payload semantics are validated before entering the canonical
event model while preserving the DB gate as the sole authority for identity,
deduplication, and overlap rules.


## Phase 24 — OTA Modification Semantics (Closed)

Goal:
Introduce explicit semantic recognition for OTA modification events
without violating the deterministic ingestion contract.

Completed:

- Added intermediate OTA semantic kind: MODIFY
- Extended Booking.com adapter support for reservation_modified
- Prevented unresolved modification events from silently falling into
  CREATE or CANCEL semantics
- Enforced deterministic rejection at adapter boundary when payload-only
  resolution is not available

Outcome:

The system can now recognize OTA modification events explicitly while
preserving deterministic ingestion and canonical DB gate authority.

## Phase 25 — OTA Modification Resolution Rules (Active)

Goal:
Define deterministic adapter-side rules for when OTA modification events
may be safely resolved from payload semantics.

Focus:

- identify whether Booking.com payloads contain enough deterministic
  information for safe modification resolution
- allow only payload-deterministic single-envelope outcomes
- reject ambiguous modification events deterministically
- preserve the one normalized event -> one canonical envelope contract

Constraint:

Multi-envelope outcomes such as CANCEL + CREATE remain out of scope
unless the adapter contract is explicitly expanded in a later phase.


---------------------------------------------------------------------

Future Improvements — OTA Sync Recovery Layer

(possible future feature name: Channel Reconciliation Engine)

Background

Certain OTA providers (for example Booking.com) emit modification
notifications that do not represent a deterministic lifecycle event.
These notifications often indicate that a reservation may have changed,
but the payload alone does not prove the semantic meaning of the change.

Typical examples include:

reservation_modified
reservation_updated
reservation_changed

In many OTA ecosystems these events function only as change
notifications and require a follow-up reservation retrieval in order
to determine the true semantic meaning of the change.

This creates a mismatch with the iHouse canonical event model, which
requires that every event entering the canonical pipeline has a
deterministic meaning.


Architectural Principle

The canonical event model must only accept deterministic facts.

The canonical system must never interpret ambiguous OTA modification
notifications as lifecycle transitions such as UPDATE, CREATE, or CANCEL
unless the provider payload alone proves the meaning unambiguously.

For this reason, unresolved OTA modification events are rejected at the
adapter boundary.


Phase 25 Outcome

The system retains explicit recognition of OTA modification events
through the semantic class:

MODIFY

However, unless a deterministic interpretation can be proven from the
provider payload alone, modification events are rejected by default.

MODIFY
→ deterministic reject


Future Direction

A future architectural layer may be introduced outside the canonical
event ingestion boundary.

This layer is referred to as the OTA Sync Recovery Layer
(possible future product name: Channel Reconciliation Engine).


Purpose

The OTA Sync Recovery Layer provides a controlled mechanism to handle
provider change notifications that require external context or
reservation re-fetch operations.

This layer operates outside the canonical event model and must never
mutate canonical booking state directly.


Possible Responsibilities

The OTA Sync Recovery Layer may perform operations such as:

- detecting OTA modification notifications
- triggering reservation re-fetch operations
- retrieving updated reservation snapshots
- comparing OTA snapshots with local state
- producing deterministic reconciliation outcomes


Canonical Safety Rule

Any reconciliation result must produce a deterministic canonical event
before entering the canonical ingestion pipeline.

The recovery layer itself must not bypass the canonical apply gate.


Example Flow

OTA notification received:

reservation_modified


Recovery workflow:

notification
→ fetch reservation from OTA
→ compare with local snapshot
→ determine deterministic change


Possible canonical outcomes:

UPDATE
CANCEL
or
no canonical change


Only the deterministic outcome may enter the canonical pipeline.


Goal

This design preserves the integrity of the canonical event model while
allowing the system to safely integrate OTA ecosystems that rely on
synchronization-based change notifications rather than deterministic
lifecycle events.



---------------------------------------------------------------------

Phase 25 – OTA Modification Resolution Rules (Closed)

The system introduced explicit semantic recognition for OTA
modification events using the semantic event class MODIFY.

Inspection of provider payload structures demonstrated that OTA
modification notifications cannot be deterministically interpreted
without external state context.

To preserve the deterministic event model the canonical ingestion rule
remains:

MODIFY
→ deterministic reject-by-default


Phase 26 – OTA Provider Verification (Active)

This phase verifies whether OTA providers expose deterministic payload
signals capable of supporting safe payload-only interpretation of
modification events.

No canonical behavior changes are introduced in this phase.


## Phase 26 — OTA Provider Verification (Closed)

Verified OTA provider payload schemas to determine whether
modification events expose deterministic semantic subtypes.

Providers inspected:

Booking.com  
Expedia  
Airbnb  
Agoda  
Trip.com

Result

No deterministic payload-only modification subtype exists.

Canonical rule confirmed:

MODIFY  
→ deterministic reject-by-default


## Phase 27 — Multi-OTA Adapter Architecture (Active)

Introduce a scalable adapter architecture for multiple OTA providers
while preserving the deterministic ingestion pipeline and canonical
database gate authority.

## Phase 27 — Multi-OTA Adapter Architecture (Closed)

Goal:
Introduce a scalable adapter architecture for multiple OTA providers
while preserving the deterministic ingestion pipeline and canonical
database gate authority.

Completed:

- Added a shared OTA orchestration pipeline:
  - src/adapters/ota/pipeline.py
- Refactored src/adapters/ota/service.py so the service acts as an
  entrypoint and delegates orchestration to the shared pipeline
- Extended src/adapters/ota/registry.py to support multiple providers
- Preserved provider-isolated adapter modules
- Added an Expedia scaffold adapter to validate multi-provider
  extensibility without changing the shared pipeline or DB gate

Validation:

- Existing test suite remained green after the refactor
- Multi-provider adapter registration now works without modifying
  semantics.py, validator.py, or apply_envelope behavior

Result:

The OTA adapter architecture is now multi-provider at the shared
pipeline and registry level.

Important precision:

- Booking.com remains the concrete provider implementation
- Expedia was added as an architectural scaffold adapter
- Airbnb, Agoda, and Trip.com were not implemented in this phase

Architectural invariants preserved:

- apply_envelope remains the only write authority
- booking_state remains projection-only
- MODIFY remains deterministic reject-by-default
- provider-specific logic remains isolated from the shared pipeline


## Future Improvements — OTA External Surface Hardening

Background

The OTA boundary currently emits a single external canonical envelope
kind:

BOOKING_SYNC_INGEST

This may be sufficient for the current architecture, but as additional
providers are added it may become too implicit and allow semantic
ambiguity to accumulate in payload structure rather than in the
external canonical surface itself.

Future Direction

A later hardening phase should explicitly decide whether the OTA
external surface remains a single external kind or is split into more
explicit deterministic kinds aligned with semantic outcomes such as:

CREATE
CANCEL

Architectural rule

This decision must occur before large scale provider expansion.

It should be resolved before implementing multiple real providers
beyond the current architectural scaffold stage.

Constraints

Any future surface split must preserve:

- apply_envelope as the single write gate
- booking_state as projection-only
- deterministic replay behavior
- provider isolation
- MODIFY → deterministic reject-by-default


## Future Improvements — OTA Retry Business Idempotency

Background

Envelope idempotency protects transport-level retries, but future OTA
integrations may send repeated business events with different request
identifiers.

Future Direction

A later hardening phase may introduce a dedicated business idempotency
layer or registry for OTA-originated events.

This should occur before high volume production OTA traffic.


## Future Improvements — OTA Out-of-Order Event Handling

Background

Distributed OTA integrations may deliver deterministic events out of
order.

Examples include cancellation notifications arriving before creation
notifications or delayed delivery of older business events.

Future Direction

A later phase may introduce controlled handling such as buffering,
guarded state machines, or recovery workflows.

This must occur after the external surface decision is resolved and
must remain outside the current adapter contract unless formally
promoted into a new canonical layer.


## Future Improvements — OTA Sync Recovery Layer

Background

Certain OTA providers emit state synchronization signals rather than
deterministic lifecycle facts.

Typical examples include modification notifications that require
provider snapshot retrieval and state comparison.

Future Direction

A later architectural layer may introduce a controlled OTA Sync
Recovery Layer outside the canonical ingestion boundary.

Constraints

The recovery layer must never mutate canonical state directly.

Any reconciliation result must still enter the system only through the
canonical apply gate after becoming a deterministic canonical fact.

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

## Phase 28 — OTA External Surface Canonicalization (Closed)

Goal

Resolve the ambiguity in the OTA external ingestion surface before
expanding real provider integrations.

Background

The OTA boundary previously emitted a single external envelope kind:

BOOKING_SYNC_INGEST

This envelope acted as a transport container and required payload
inspection to determine the semantic meaning of the event.

While functional, this design hid business semantics inside payload
fields rather than representing them explicitly in the canonical
event surface.

Architectural Question

Should the OTA ingestion boundary continue emitting a single
transport-style envelope, or should adapters emit explicit
canonical business events representing deterministic lifecycle facts?

Decision

The system adopts explicit canonical lifecycle events.

OTA adapters must emit:

BOOKING_CREATED  
BOOKING_CANCELED

The transport envelope:

BOOKING_SYNC_INGEST

is no longer considered a canonical external event surface.

Rationale

Explicit lifecycle events improve:

- event log readability
- auditability
- deterministic reasoning about the ledger
- multi-provider scalability

The canonical event log must represent domain facts rather than
integration transport containers.

Implementation Impact

The OTA adapter contract is updated so that semantic classification
directly produces canonical lifecycle events.

CREATE → BOOKING_CREATED  
CANCEL → BOOKING_CANCELED

OTA modification notifications continue to follow the invariant:

MODIFY  
→ deterministic reject-by-default

Architectural Invariants Preserved

This decision does not modify the canonical system authority model.

The following invariants remain unchanged:

- apply_envelope remains the single write authority
- event_log remains append-only
- booking_state remains projection-only
- adapters must not read booking_state
- adapters must not reconcile booking history
- adapters must not mutate canonical state

Outcome

The external OTA ingestion surface now emits explicit canonical
business facts rather than transport envelopes.

This aligns the external integration boundary with the canonical
event model and prepares the architecture for safe expansion to
multiple OTA providers.

## Future Improvement – Removal of Transport Artifact

Background

Prior to Phase 28 the OTA boundary emitted a generic transport
envelope called:

BOOKING_SYNC_INGEST

Phase 28 replaced this external surface with explicit canonical
lifecycle events:

BOOKING_CREATED
BOOKING_CANCELED

Current Status

The historical transport event may still exist internally in parts
of the OTA adapter execution pipeline.

Future Direction

A later cleanup phase may remove this artifact once the execution
pipeline no longer depends on the historical transport container.
## Phase 29 — OTA Ingestion Replay Harness (Closed)

Completed:
- Added deterministic OTA replay verification as test tooling.
- Verified replay path through:
  - ingest_provider_event
  - canonical envelope creation
  - CoreExecutor.execute
- Added replay coverage for:
  - BOOKING_CREATED
  - BOOKING_CANCELED
  - duplicate replay
  - MODIFY rejection
  - invalid payload rejection
- Performed minimal OTA contract alignment required for replay execution.

Outcome:
- OTA replay behavior is now verifiable through the canonical execution path.
- apply_envelope remains the single write authority.
- Canonical invariants remain unchanged.

## Phase 30 – OTA Ingestion Interface Hardening

Status:
Active

Summary:
Hardened the OTA ingestion interface by locking the explicit runtime
handoff from provider-facing OTA entry through shared OTA processing,
canonical envelope construction, IngestAPI.ingest, and
CoreExecutor.execute, while preserving apply_envelope as the sole write
authority and keeping MODIFY deterministic reject-by-default.

Confirmed runtime handoff:
- ingest_provider_event
- process_ota_event
- canonical envelope
- IngestAPI.ingest
- CoreExecutor.execute
- apply_envelope

Outcome:
- OTA service entry remains thin
- shared OTA pipeline owns normalization, validation, classification,
  and envelope construction
- provider adapters remain provider-specific only
- core ingest API remains the explicit bridge into execution
- CoreExecutor remains the single execution boundary
- canonical invariants remain unchanged

## Documentation Rule Update — Future Improvements

Future-looking improvements, deferred hardening items, and backlog notes
are no longer to be added as new content inside this phase timeline.

This file remains append-only historical phase chronology.

Historical future-improvement notes remain in older entries as part of
the permanent record.

From this point forward, new future improvements must be recorded in:

- docs/core/improvements/future-improvements.md

## Phase 31 — Closed

Status:
Closed

Summary:
Phase 31 closed the documentation and interface-verification loop for
the OTA ingestion contract without changing canonical business
semantics.

Confirmed runtime handoff:
- ingest_provider_event
- process_ota_event
- canonical envelope
- IngestAPI.append_event
- CoreExecutor.execute
- apply_envelope

Outcome:
- active docs aligned to the live runtime contract
- contract-name drift removed from current-state documentation
- OTA service wording clarified to core-ingest terminology
- closed phase specs archived consistently
- dedicated future improvements backlog introduced
- no new write path introduced
- canonical semantics unchanged

Next phase:
Phase 32 – OTA Ingestion Contract Test Verification

## Phase 32 — OTA Ingestion Contract Test Verification (Closed)

Status:
Closed

Summary:
Phase 32 closed the executable verification loop for the OTA ingestion runtime contract without changing canonical business semantics.

Confirmed runtime handoff:
- ingest_provider_event
- process_ota_event
- canonical envelope
- IngestAPI.append_event
- CoreExecutor.execute
- apply_envelope

Outcome:
- direct tests added for thin OTA service entry
- direct tests added for ordered shared OTA pipeline responsibilities
- direct tests added for core ingest rejection of missing executor wiring
- replay verification aligned to the same public ingest contract
- no tested OTA runtime path bypasses core ingest or CoreExecutor
- relevant smoke and invariant checks rerun successfully
- no new write path introduced
- canonical semantics unchanged

Next phase:
Phase 33 — OTA Retry Business Idempotency Discovery

## Phase 33 — OTA Retry Business Idempotency Discovery (Closed)

Status:
Closed

Summary:
Phase 33 closed the OTA retry business idempotency discovery loop and established that the strongest verified risk is runtime routing and emitted-event alignment, not a proven intrinsic failure of canonical Supabase business dedup.

Confirmed discovery outcome:
- OTA transport idempotency currently derives from provider external_event_id
- canonical Supabase business protection already exists for canonical emitted business events
- apply_envelope performs canonical BOOKING_CREATED and BOOKING_CANCELED handling from emitted events
- the active OTA runtime path currently appears misaligned with the canonical emitted business event contract expected by apply_envelope

Outcome:
- transport idempotency and canonical business identity enforcement were separated clearly
- the active risk was narrowed to runtime mapping and routing alignment
- no canonical business semantics changed
- no alternative write path introduced
- no closed semantic decision was reopened

Next phase:
Phase 34 — OTA Canonical Event Emission Alignment

## Phase 34 — OTA Canonical Event Emission Alignment (Closed)

Status:
Closed

Summary:
Phase 34 proved a routing and emitted-event alignment gap in the active OTA runtime path. It established that `BOOKING_CREATED` routes to a noop skill and `BOOKING_CANCELED` has no active route, preventing activation of canonical Supabase business logic.

Confirmed discovery outcome:
- [Claude]
- `BOOKING_CREATED` verified routing to `booking-created-noop` (emits zero events).
- `BOOKING_CANCELED` verified as having no active route (raises `NO_ROUTE`).
- Payload shape mismatch verified: OTA envelope payload does not match emitted event payload expected by `apply_envelope`.

Outcome:
- Minimal alignment change defined: Two new skills + registry updates.
- No intrinsic failure of canonical Supabase business dedup was proven.
- No architecture redesign was justified.
- All 5 required questions answered with evidence.

Next phase:
Phase 35 — OTA Canonical Emitted Event Alignment Implementation
## Phase 35 — OTA Canonical Emitted Event Alignment Implementation (Closed)

Status:
Closed

Summary:
Phase 35 implemented the minimal alignment defined by Phase 34. OTA-originated BOOKING_CREATED and BOOKING_CANCELED now reach apply_envelope through the canonical emitted business event contract. The Phase 34 alignment gap is resolved.

Completed:
- [Claude]
- booking_created skill: transforms OTA payload → canonical BOOKING_CREATED emitted event
- booking_canceled skill: emits BOOKING_CANCELED with booking_id
- registry updates: kind_registry and skill_exec_registry updated for both event types
- 17 contract tests added and passing
- E2E verified against live Supabase: BOOKING_CREATED and BOOKING_CANCELED both return status APPLIED with state_upsert_found true

Outcome:
- OTA booking lifecycle events now activate canonical Supabase business logic
- booking_state is written by apply_envelope upon canonical emitted events
- no canonical invariants violated
- no architecture redesign
- 30 tests pass (2 pre-existing SQLite failures unrelated)

Next phase:
Phase 36 — TBD
## Phase 36 — Business Identity Canonicalization (Closed)

Status:
Closed

Summary:
Phase 36 verified and formally documented the canonical booking_id construction rule and confirmed that apply_envelope already provides sufficient business-level duplicate protection.

Confirmed:
- [Claude]
- booking_id rule: {source}_{reservation_ref} — deterministic and consistent across all active skills
- apply_envelope dedup: two layers — by booking_id, and by composite (tenant_id, source, reservation_ref, property_id)
- E2E verified: duplicate BOOKING_CREATED with different request_id returns ALREADY_EXISTS without writing a new booking_state row
- backlog items Business Idempotency and Business Identity Enforcement marked resolved
- Phase 33 follow-up note resolved

Outcome:
- canonical booking_id rule formally documented
- no additional business-idempotency registry required at this stage
- no canonical business semantics changed
- no alternative write path introduced

Next phase:
Phase 37 — TBD
## Phase 37 — External Event Ordering Protection Discovery (Closed)

Status:
Closed

Summary:
Phase 37 verified the current system behavior when OTA events arrive out of order. It classified the current behavior as deterministic rejection, not silent data loss.

Confirmed:
- [Claude]
- BOOKING_CANCELED before BOOKING_CREATED → apply_envelope raises BOOKING_NOT_FOUND (P0001) — deterministic rejection
- no buffering, retry, or ordering layer exists in the active OTA runtime path
- correct-order flow (CREATED then CANCELED) verified unaffected — no regression
- E2E evidence: code P0001, message BOOKING_NOT_FOUND
- backlog item External Event Ordering Protection updated with verified behavioral description

Outcome:
- current behavior is safe in terms of canonical invariants: no silent writes, no state corruption
- the rejected event is lost — no dead-letter store or retry queue exists
- this is a known open gap, remains deferred in future-improvements.md
- priority: high for future implementation phase

Next phase:
Phase 38 — TBD
## Phase 38 — Dead Letter Queue for Failed OTA Events (Closed)

Status:
Closed

Summary:
Phase 38 implemented a minimal, append-only Dead Letter Queue so that OTA events rejected by apply_envelope are preserved for investigation and future replay instead of being silently lost.

Completed:
- [Claude]
- Supabase table `ota_dead_letter` created via migration (append-only, RLS for service_role)
- `dead_letter.py` module: best-effort, non-blocking DLQ write, swallows all errors, logs WARNING to stderr on failure
- `service.py` updated: `ingest_provider_event_with_dlq` added, original thin wrapper preserved
- 6 contract tests added and passing
- E2E verified: BOOKING_CANCELED before CREATED → DLQ row written with rejection_code BOOKING_NOT_FOUND

Outcome:
- rejected OTA events are now preserved, not lost
- DLQ is append-only, never bypasses apply_envelope, never mutates canonical state
- 36 tests pass (2 pre-existing SQLite failures unrelated)

Next phase:
Phase 39 — TBD
## Phase 39 — DLQ Controlled Replay (Closed)

Status:
Closed

Summary:
Phase 39 implemented a safe, idempotent, manually-triggered replay mechanism for ota_dead_letter rows, making DLQ events actionable for the first time.

Completed:
- [Claude]
- Migration: replayed_at, replay_result, replay_trace_id added to ota_dead_letter
- dlq_replay.py: replay_dlq_row(row_id) — always routes through apply_envelope, never bypasses canonical gate
- Idempotency: successfully-replayed rows return previous result without re-processing
- New idempotency key: each replay uses a fresh request_id (dlq-replay-{id}-{hex})
- Outcome persistence: replayed_at, replay_result, replay_trace_id written back to DLQ row
- 7 contract tests added
- E2E verified end-to-end
- future-improvements.md updated with 4 new forward-looking items

Outcome:
- 43 tests pass (2 pre-existing SQLite failures unrelated)
- No automatic retry introduced
- No canonical write path bypassed

Next phase:
Phase 40 — TBD
## Phase 40 — DLQ Observability (Closed)

Status:
Closed

Summary:
Phase 40 introduced a read-only inspection layer for ota_dead_letter, making DLQ state visible to operators via a Supabase view and Python utility functions.

Completed:
- [Claude]
- Migration: ota_dlq_summary view — groups by event_type + rejection_code, counts total/pending/replayed
- dlq_inspector.py: get_pending_count(), get_replayed_count(), get_rejection_breakdown()
- 11 contract tests, all unit-mocked
- E2E verified against live Supabase

Outcome:
- 54 tests pass (2 pre-existing SQLite failures unrelated)
- No write paths added
- No booking_state reads

Next phase:
Phase 41 — DLQ Alerting Threshold
## Phase 41 — DLQ Alerting Threshold (Closed)

Status:
Closed

Summary:
Phase 41 added a configurable threshold check on DLQ pending count with structured WARNING logging.

Completed:
- [Claude]
- DLQAlertResult frozen dataclass
- check_dlq_threshold(threshold, client) — emits [DLQ ALERT] to stderr when pending >= threshold
- check_dlq_threshold_default() — reads DLQ_ALERT_THRESHOLD env var, defaults to 10
- 13 contract tests

Outcome:
- 67 tests pass (2 pre-existing SQLite failures unrelated)
- No Supabase migrations
- No write paths

Next phase:
Phase 42 — Reservation Amendment Discovery
## Phase 42 — Reservation Amendment Discovery (Closed)

Status:
Closed

Type:
Discovery only — no code, no schema changes, no new tests

Summary:
Phase 42 systematically investigated all preconditions for introducing BOOKING_AMENDED. Findings show 3 of 10 prerequisites are satisfied and 7 gaps remain.

Key findings:
- MODIFY classification already in semantics.py (deterministic, stateless)
- Both adapters already classify MODIFY but reject at to_canonical_envelope
- Amendment payload structure not normalized across providers
- apply_envelope needs: BOOKING_AMENDED enum + lifecycle guard + field merge branch
- booking_state has no explicit status column (ACTIVE/CANCELED)
- DLQ replay exists but has no booking-level ordering constraint
- booking_id is stable across amendment events ✅

MODIFY remains deterministic reject-by-default.

Next phase:
Phase 43 — booking_state Status Column
## Phase 43 — booking_state Status Verification (Closed)

Status:
Closed

Summary:
Phase 43 corrected a Phase 42 finding: booking_state.status already exists and is correctly managed by apply_envelope. Phase 43 verified this E2E and added a read-only status inspection utility.

Key correction:
Phase 42 incorrectly claimed status column was missing. The column was always there (status='active' on CREATED, 'canceled' on CANCELED). The gap was in exposure and verification, not in schema.

Completed:
- [Claude]
- E2E: status=active after CREATED, status=canceled after CANCELED on live Supabase ✅
- booking_status.py: get_booking_status(booking_id) — read-only, never used in ingestion path
- 9 contract tests
- future-improvements.md: BOOKING_AMENDED prerequisites updated to 4/10

Outcome:
- 76 tests pass
- No schema changes
- Amendment prerequisites: 4/10 satisfied

Next phase:
Phase 44 — TBD (Amendment prerequisite: Normalized AmendmentPayload, or external event ordering buffer)
## Phase 44 — OTA Ordering Buffer (Closed)

Status:
Closed

Summary:
Phase 44 introduced the ordering buffer — a structured staging area for out-of-order OTA events that arrived before their prerequisite BOOKING_CREATED.

Completed:
- [Claude]
- Migration: ota_ordering_buffer table with FK, status constraint, index, RLS
- ordering_buffer.py: buffer_event, get_buffered_events, mark_replayed
- 10 contract tests
- E2E verified on live Supabase

Outcome:
- 86 tests pass
- Ordering-blocked events now explicitly tracked by booking_id
- Auto-trigger on BOOKING_CREATED is Phase 45

Next phase:
Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED
## Phase 45 — Ordering Buffer Auto-Trigger on BOOKING_CREATED (Closed)

Status:
Closed

Summary:
Phase 45 completed the event ordering loop. After a successful BOOKING_CREATED, the system automatically replays any events that were buffered in ota_ordering_buffer as ordering-blocked.

Completed:
- [Claude]
- ordering_trigger.py: trigger_ordered_replay — read, replay, mark, log failures, return summary
- service.py: trigger fires after BOOKING_CREATED APPLIED (best-effort, non-blocking)
- 7 contract tests
- E2E: CANCELED → buffer → CREATED → auto-trigger → 0 waiting confirmed

Outcome:
- 93 tests pass
- Ordering loop closed: Phases 44+45 together form the full event ordering buffer system

Next phase:
Phase 46 — TBD
## Phase 46 — System Health Check (Closed)

Status:
Closed

Rationale:
Large SaaS companies (Stripe, Twilio) build a system health check before expanding feature surface. Before BOOKING_AMENDED or production deployment, iHouse Core needed one callable that tells operators if the system is healthy.

Completed:
- [Claude]
- ComponentStatus + HealthReport frozen dataclasses
- system_health_check(): 5 components, never raises, structured readiness report
- 10 contract tests
- E2E: OVERALL OK ✅ on live Supabase in under 1 second

Outcome:
- 103 tests pass
- No migration, no new tables
- System is now production-ready for the current feature set

Next phase:
Phase 47 — TBD (Normalized AmendmentPayload / OTA Payload Validation)
## Phase 47 — OTA Payload Boundary Validation (Closed)

Status:
Closed

Rationale:
Every production API validates inputs at the boundary before canonical processing. Phase 47 adds explicit, structured validation before normalize() — rejections now have error codes, not opaque stack traces.

Completed:
- [Claude]
- payload_validator.py: PayloadValidationResult frozen dataclass, validate_ota_payload with 6 rules, all errors collected
- pipeline.py: boundary validation at top of process_ota_event
- 16 contract tests
- Updated pre-existing pipeline test for backward compat

Outcome:
- 119 tests pass
- BOOKING_AMENDED prerequisite: normalized validation layer now exists
- Amendment payloads can use same validator skeleton when implemented

Next phase:
Phase 48 — TBD
## Phase 48 — Idempotency Key Standardization (Closed)

Status:
Closed

Rationale:
Stripe-style idempotency: keys must be namespaced and collision-safe. Raw external_event_id was shared across providers and event types.

Completed:
- [Claude]
- idempotency.py: generate_idempotency_key + validate_idempotency_key
- Format: provider:event_type:event_id (lowercase, deterministic)
- Both adapters updated
- 19 contract tests
- Updated harness tests for new format

Outcome:
- 138 tests pass
- Cross-provider and cross-type key collisions are impossible
- Key format is ready for BOOKING_AMENDED events when implemented

Next phase:
Phase 49 — TBD
## Phase 49 — Normalized AmendmentPayload Schema (Closed)

Status:
Closed

Rationale:
Before apply_envelope can handle BOOKING_AMENDED, the system needs a canonical, provider-agnostic schema for what changed in an amendment.

Completed:
- [Claude]
- AmendmentFields frozen dataclass (schemas.py): new_check_in, new_check_out, new_guest_count, amendment_reason
- amendment_extractor.py: Booking.com and Expedia extractors + normalize_amendment dispatcher
- 15 contract tests

Outcome:
- 153 tests pass
- BOOKING_AMENDED prerequisites: 7/10 (Normalized Schema ✅)
- Phase 50 can implement apply_envelope BOOKING_AMENDED branch

Next phase:
Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch

## Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch (Closed)

Status:
Closed

Summary:
Phase 50 completed the SQL/stored-procedure layer for BOOKING_AMENDED and verified it E2E on live Supabase before Phase 51. All 10 BOOKING_AMENDED prerequisites are now satisfied.

Completed:
- Step 1 (prior chat): ALTER TYPE event_kind ADD VALUE 'BOOKING_AMENDED' — already live ✅
- Step 2: Deployed via supabase CLI (`supabase db push`), migration `20260308210000_phase50_step2_apply_envelope_amended.sql`
  - CREATE OR REPLACE FUNCTION apply_envelope — full BOOKING_AMENDED branch added:
    1. booking_id guard (BOOKING_ID_REQUIRED)
    2. SELECT FOR UPDATE row lock
    3. ACTIVE-state lifecycle guard (AMENDMENT_ON_CANCELED_BOOKING)
    4. Optional new_check_in / new_check_out extraction
    5. Date validation when both provided
    6. Append-only STATE_UPSERT to event_log
    7. UPDATE booking_state with COALESCE (preserves existing dates if not supplied), status stays 'active'
- Written tests/test_booking_amended_e2e.py — 5 E2E tests, all passing on live Supabase:
  - BOOKING_CREATED → APPLIED ✅
  - BOOKING_AMENDED both dates → APPLIED, check_in/check_out updated, status=active, version=2 ✅
  - BOOKING_AMENDED partial (check_in only) → check_in updated, check_out preserved via COALESCE ✅
  - BOOKING_AMENDED on CANCELED → AMENDMENT_ON_CANCELED_BOOKING ✅
  - BOOKING_AMENDED on non-existent booking → BOOKING_NOT_FOUND ✅

Outcome:
- BOOKING_AMENDED prerequisites: 10/10 ✅
- apply_envelope remains the single verified write authority for all lifecycle events
- 158 tests pass (2 pre-existing SQLite failures unrelated)
- No canonical invariants changed
- No alternative write path introduced

Next phase:
Phase 51 — Python Pipeline Integration (semantics.py + service.py BOOKING_AMENDED routing)

## Phase 58 — HTTP Ingestion Layer (Closed)

Created FastAPI HTTP endpoint as the real production boundary for OTA webhook ingestion.

Files added:
- src/api/__init__.py
- src/api/webhooks.py — POST /webhooks/{provider}
- tests/test_webhook_endpoint.py — 16 contract tests

HTTP status codes locked:
- 200 ACCEPTED — envelope created, idempotency_key returned
- 400 PAYLOAD_VALIDATION_FAILED — with codes list
- 403 SIGNATURE_VERIFICATION_FAILED — HMAC mismatch or unknown provider
- 500 INTERNAL_ERROR — unexpected exception (internals never surfaced)

Result: 286 passed, 2 skipped.

## Phase 59 — FastAPI App Entrypoint (Closed)

Created src/main.py — unified production entrypoint.

Files added:
- src/main.py — FastAPI app with lifespan, GET /health, mounts webhooks router
- tests/test_main_app.py — 6 contract tests

app/main.py unchanged.
Result: 292 passed, 2 skipped.

## Phase 60 — Structured Request Logging Middleware (Closed)

Added request logging middleware to src/main.py.

Every request gets:
- UUID4 request_id (stored in request.state)
- → entry log line (method + path)
- ← exit log line (method + path + status + duration_ms)
- X-Request-ID response header

Files changed: src/main.py (middleware added)
Files added: tests/test_logging_middleware.py (7 contract tests)
Result: 299 passed, 2 skipped.

## Phase 61 — JWT Auth Middleware (Closed)

tenant_id moved from OTA payload body to verified JWT Bearer token (sub claim).

Files added: src/api/auth.py, tests/test_auth.py
Files modified: src/api/webhooks.py, src/adapters/ota/payload_validator.py,
                tests/test_payload_validator_contract.py, tests/test_webhook_endpoint.py

TENANT_ID_REQUIRED removed from payload_validator (constant kept, rule removed).
Result: 307 passed, 2 skipped.

## Phase 62 — Per-Tenant Rate Limiting (Closed)

Added sliding-window in-memory rate limiter keyed by tenant_id (from JWT).

Files added: src/api/rate_limiter.py, tests/test_rate_limiter.py
Files modified: src/api/webhooks.py (Depends(rate_limit) added)

Limit: IHOUSE_RATE_LIMIT_RPM (default 60/min/tenant). Dev bypass at 0.
429 with Retry-After header on excess.
Result: 313 passed, 2 skipped.

HTTP API layer complete (Phases 58-62):
  58 — POST /webhooks/{provider} endpoint
  59 — FastAPI app entrypoint
  60 — Request logging middleware
  61 — JWT auth
  62 — Per-tenant rate limiting

## Phase 63 — OpenAPI Docs (Closed)

Enriched /docs and /redoc to production quality.

Files added: src/schemas/__init__.py, src/schemas/responses.py, docs/archive/phases/phase-63-spec.md
Files modified: src/main.py (API metadata, BearerAuth scheme), src/api/webhooks.py (response schemas)

Result: 313 passed, 2 skipped.

## Phase 64 — Enhanced Health Check (Closed)

GET /health enriched with real dependency checks.

Files added: src/api/health.py, tests/test_health.py
Files modified: src/main.py, src/schemas/responses.py

Status: ok / degraded (DLQ>0, 200) / unhealthy (Supabase down, 503)
Result: 320 passed, 2 skipped.

## Phase 65 — Financial Data Foundation (Closed)

Introduced structured financial field extraction for all 5 OTA adapters.

Files added: src/adapters/ota/financial_extractor.py, tests/test_financial_extractor_contract.py
Files modified: src/adapters/ota/schemas.py, src/adapters/ota/bookingcom.py, src/adapters/ota/expedia.py, src/adapters/ota/airbnb.py, src/adapters/ota/agoda.py, src/adapters/ota/tripcom.py

BookingFinancialFacts: frozen dataclass (immutable, validated).
source_confidence: FULL | PARTIAL | ESTIMATED per provider.
Invariant enforced: financial_facts never enters canonical envelope or booking_state.
Result: 372 passed, 2 skipped.

## Phase 66 — booking_financial_facts Supabase Projection (Closed)

Persists structured financial facts to Supabase after successful BOOKING_CREATED events.

Files added: src/adapters/ota/financial_writer.py, tests/test_financial_writer_contract.py, scripts/migrate_phase66_financial_facts.py, docs/archive/phases/phase-66-spec.md
Files modified: src/adapters/ota/service.py (financial write after BOOKING_CREATED APPLIED)
DB: booking_financial_facts table (append-only, RLS, 2 indexes)

Invariant enforced: booking_state must NEVER contain financial data. This is a separate projection table.
E2E verified: BOOKING_CREATED → booking_financial_facts row written to live Supabase.
Result: 388 passed, 2 skipped.

## Phase 67 — Financial Facts Query API (Closed)

Exposes booking_financial_facts via GET /financial/{booking_id}. JWT auth + tenant isolation enforced.

Files added: src/api/financial_router.py, tests/test_financial_router_contract.py, docs/archive/phases/phase-67-spec.md
Files modified: src/main.py (financial tag + router registered)

Invariant: endpoint reads from booking_financial_facts ONLY. Never touches booking_state.
Result: 396 passed, 2 skipped.




## Phase 68 — booking_id Stability (Closed)

Introduced `booking_identity.py` — a pure, deterministic normalization module for `reservation_ref` values.

All 5 OTA adapters now call `normalize_reservation_ref(provider, raw_ref)` in `normalize()` before constructing `reservation_id`. The locked formula `booking_id = {source}_{reservation_ref}` (Phase 36) is unchanged.

Files added:
- `src/adapters/ota/booking_identity.py` — `normalize_reservation_ref` + `build_booking_id`
- `tests/test_booking_identity_contract.py` — 30 contract tests

Files modified:
- `src/adapters/ota/bookingcom.py` — normalize() uses normalize_reservation_ref
- `src/adapters/ota/expedia.py` — normalize() uses normalize_reservation_ref
- `src/adapters/ota/airbnb.py` — normalize() uses normalize_reservation_ref
- `src/adapters/ota/agoda.py` — normalize() uses normalize_reservation_ref (booking_ref)
- `src/adapters/ota/tripcom.py` — normalize() uses normalize_reservation_ref (order_id)
- `docs/core/improvements/future-improvements.md` — DLQ items (Phases 39-41) and booking_id Stability marked resolved

Result: 431 passed, 2 skipped.
No Supabase schema changes.

## Phase 69 — BOOKING_AMENDED Python Pipeline (Closed)

Wired the Python pipeline so BOOKING_AMENDED events flow end-to-end from OTA webhook to apply_envelope.

Also performed full backlog audit: marked 3 additional items resolved in future-improvements.md:
- External Event Ordering Protection (already done Phases 44-45)
- External Event Signature Validation (already done Phase 57)
- BOOKING_AMENDED Support (now complete)

Files added:
- `src/core/skills/booking_amended/__init__.py` — package marker
- `src/core/skills/booking_amended/skill.py` — COALESCE-safe emitted event builder
- `tests/test_booking_amended_skill_contract.py` — 20 contract tests

Files modified:
- `src/core/kind_registry.core.json` — BOOKING_AMENDED → booking-amended
- `src/core/skill_exec_registry.core.json` — booking-amended → core.skills.booking_amended.skill
- `src/adapters/ota/service.py` — BOOKING_AMENDED financial facts write (best-effort)
- `docs/core/improvements/future-improvements.md` — 3 items marked resolved

Result: 451 passed, 2 skipped.
No Supabase schema changes.

## Phase 71 — Booking State Query API (Closed)

GET /bookings/{booking_id} — reads booking_state projection with JWT auth + tenant isolation.

Files added:
- `src/api/bookings_router.py` — GET /bookings/{booking_id}
- `tests/test_bookings_router_contract.py` — 16 contract tests
- `docs/archive/phases/phase-71-spec.md`

Files modified:
- `src/main.py` — bookings tag + bookings_router registered

API contract:
- 200 → booking_id, tenant_id, source, reservation_ref, property_id, status, check_in, check_out, version, created_at, updated_at
- 404 → BOOKING_NOT_FOUND (cross-tenant also returns 404, not 403)
- 500 → INTERNAL_ERROR

Invariants: reads booking_state only, no write path, tenant isolation enforced at DB query level.
Result: 467 passed, 2 skipped.

## Phase 72 — Tenant Summary Dashboard (Closed)

GET /admin/summary — real-time operational summary, tenant-scoped.

Files added:
- `src/api/admin_router.py` — GET /admin/summary (7 response fields)
- `tests/test_admin_router_contract.py` — 14 contract tests
- `docs/archive/phases/phase-72-spec.md`

Files modified:
- `src/main.py` — admin tag + admin_router registered

Response fields: tenant_id, active_bookings, canceled_bookings, total_bookings,
dlq_pending (global), amendment_count (tenant), last_event_at (tenant).
DLQ count is global infra metric; all booking data is tenant-scoped.
Result: 481 passed, 2 skipped.

## Phase 73 — Ordering Buffer Auto-Route (Closed)

BOOKING_NOT_FOUND → Ordering Buffer Auto-Route: bufferable events (BOOKING_CANCELED, BOOKING_AMENDED) are now automatically buffered for replay when BOOKING_CREATED fires.

Files modified:
- `src/adapters/ota/service.py` — BOOKING_NOT_FOUND branch + BUFFERED status
- `src/adapters/ota/dead_letter.py` — `write_to_dlq_returning_id()` added
- `src/adapters/ota/ordering_buffer.py` — `dlq_row_id` now Optional[int]

Files added:
- `tests/test_ordering_buffer_autoroute_contract.py` — 11 contract tests
- `docs/archive/phases/phase-73-spec.md`

Result: 492 passed, 2 skipped.

## Phase 74 — OTA Date/Timezone Normalization (Closed)

date_normalizer.py normalizes all OTA date variants to canonical YYYY-MM-DD.
Integrated into all 5 provider amendment extractors.

Files added:
- `src/adapters/ota/date_normalizer.py` — normalize_date() function
- `tests/test_date_normalizer_contract.py` — 22 contract tests
- `docs/archive/phases/phase-74-spec.md`

Files modified:
- `src/adapters/ota/amendment_extractor.py` — all 5 providers now normalize dates

Formats handled: ISO date, ISO datetime (+tz, -tz, Z), compact YYYYMMDD, slash DD/MM/YYYY.
Result: 514 passed, 2 skipped.

## Phase 75 — Production Hardening: API Error Standards (Closed)

Standard error body {code, message, trace_id} across Phase 71+ routers.
X-API-Version response header added to all responses via middleware.

Files added:
- `src/api/error_models.py` — ErrorCode + make_error_response()
- `tests/test_api_error_standards_contract.py` — 19 contract tests
- `docs/archive/phases/phase-75-spec.md`

Files modified:
- `src/main.py` — X-API-Version header in middleware
- `src/api/bookings_router.py` — standard error format
- `src/api/admin_router.py` — standard error format
- `tests/test_bookings_router_contract.py` — code → error assertions
- `tests/test_admin_router_contract.py` — code → error assertions

Result: 533 passed, 2 skipped.

## Phase 76 — occurred_at vs recorded_at Separation (Closed)

Introduced `recorded_at` (server ingestion timestamp) distinct from `occurred_at` (OTA business event time).

Files modified:
- `src/adapters/ota/schemas.py` — CanonicalEnvelope.recorded_at: Optional[str] = None
- `src/adapters/ota/service.py` — stamps recorded_at = utcnow() on every envelope_dict

Files added:
- `tests/test_recorded_at_separation_contract.py` — 12 contract tests
- `docs/archive/phases/phase-76-spec.md`

Result: 545 passed, 2 skipped.

## Phase 77 — OTA Schema Normalization (Closed)

Introduced `normalize_schema(provider, payload)` in `src/adapters/ota/schema_normalizer.py`.
All 5 OTA adapters (bookingcom, airbnb, expedia, agoda, tripcom) now enrich their `NormalizedBookingEvent.payload` with three canonical keys:
- `canonical_guest_count` — unified guest count field
- `canonical_booking_ref` — unified booking reference field
- `canonical_property_id` — unified property identifier field

Raw provider fields are preserved; canonical keys are additive. Missing fields → `None` (no `KeyError`).
27 contract tests added (Groups A–E: canonical values, raw preservation, missing-field resilience).
4 existing adapter contract tests updated to use superset check (`payload.items() <= normalized.payload.items()`).

Result: 572 passed, 2 skipped.

## Phase 78 — OTA Schema Normalization (Dates + Price)

[Claude] Extended `src/adapters/ota/schema_normalizer.py` with 4 additional canonical keys:
- `canonical_check_in`   — check_in / check_in_date / arrival_date per provider
- `canonical_check_out`  — check_out / check_out_date / departure_date per provider
- `canonical_currency`   — currency (uniform across all providers)
- `canonical_total_price` — total_price / booking_subtotal / total_amount / selling_rate / order_amount per provider

All values returned as raw strings. No adapter changes required (all already call normalize_schema()).
26 new contract tests added (Groups F–I in test_schema_normalizer_contract.py).

Provider field mapping:
| Canonical Key       | bookingcom    | airbnb           | expedia        | agoda        | tripcom       |
|---------------------|---------------|------------------|----------------|--------------|---------------|
| canonical_check_in  | check_in      | check_in         | check_in_date  | check_in     | arrival_date  |
| canonical_check_out | check_out     | check_out        | check_out_date | check_out    | departure_date|
| canonical_currency  | currency      | currency         | currency       | currency     | currency      |
| canonical_total_price | total_price | booking_subtotal | total_amount   | selling_rate | order_amount  |

Result: 598 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 79 -- Idempotency Monitoring (Closed)

[Claude] Created `src/adapters/ota/idempotency_monitor.py`.
`IdempotencyReport` frozen dataclass: total_dlq_rows, pending_dlq_rows, already_applied_count,
idempotency_rejection_count, ordering_buffer_depth, checked_at.
`collect_idempotency_report()` reads ota_dead_letter + ota_ordering_buffer.
Pure read-only. Zero side effects. No new Supabase schema.
35 contract tests (Groups A-F in test_idempotency_monitor_contract.py).
`IDEMPOTENCY_REJECTION_CODES` frozenset: ALREADY_APPLIED, ALREADY_EXISTS, ALREADY_EXISTS_BUSINESS, DUPLICATE.

Result: 633 passed, 2 skipped.
No Supabase schema changes. No new migrations.

## Phase 80 -- Structured Logging Layer (Closed)

[Claude] Created `src/adapters/ota/structured_logger.py`.
StructuredLogger class: debug/info/warning/error/critical methods, each returns JSON string + emits via stdlib logging.
Entry format: {ts, level, event, trace_id?, ...kwargs}.
get_structured_logger(name, trace_id) factory.
Non-serializable values fall back via default=str. Never raises.
30 contract tests (Groups A-G in test_structured_logger_contract.py).

Result: 663 passed, 2 skipped.
No Supabase schema changes. No new migrations.
