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
