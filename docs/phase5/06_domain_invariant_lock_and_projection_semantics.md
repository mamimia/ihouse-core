# iHouse Core Phase 5.1
## 06 Domain Invariant Lock & Projection Semantics Discipline

Status: Draft
Scope: Domain meaning stability across years

### Goal
Ensure replay preserves domain meaning, not only technical determinism.

---

## 1. Core Definitions

Domain Invariant
A business truth that must remain valid across time.
Examples:
1. A booking cannot overlap another booking for the same unit and time range, unless explicitly marked as allowed overlap.
2. A booking status transition must follow an allowed graph.
3. A property must exist for any property scoped event.

Projection Semantics
The meaning of a projection row and how it is derived from canonical events.

Behavior Change
Any change that can alter domain outcomes produced from the same historical log.

---

## 2. Non Negotiable Rule

If a change would alter domain outcomes for the same historical event log,
it must be introduced as new domain events,
not as a silent edit to projection handlers.

Projection handlers may be refactored, optimized, or reorganized,
but must not change outcomes for historical logs.

---

## 3. Domain Invariant Registry

Create a central registry in code, referenced by tests and CI:

Invariant ID: stable string
Description: human readable
Scope: projection or aggregate
Proof: test name(s) that enforce it
Severity: block deploy if violated

Required minimum invariants for iHouse Core:
1. No overlap invariant for unit level availability
2. Booking state transition graph invariant
3. Event ordering invariant uses row_id ASC only
4. Idempotency invariant via event_id uniqueness
5. Property existence invariant at ingest

---

## 4. Behavior Lock Mechanism

We lock behavior with two layers:

Layer A Fingerprint Lock
Existing validate_rebuild and cross schema fingerprint equality stays mandatory.

Layer B Invariant Suite Lock
A dedicated invariant test suite must run on:
1. Seeded fixtures
2. Snapshot of a real event log sample in staging

Invariant suite must assert business truths directly, not only hashes.

---

## 5. When a Behavior Change is Legitimate

Allowed only if:
1. The old behavior is explicitly declared a bug or undesired business rule
2. The fix is introduced by new event types or new versions with explicit semantics
3. Historical events are not reinterpreted

Pattern:
1. Introduce new event type or new event version
2. Upcast old events to canonical but preserve old meaning
3. Add new events going forward to express new meaning
4. Optionally create a new projection stream keyed by behavior version

---

## 6. Optional Projection Versioning Strategy

We support projection behavior versions:

projection_behavior_version: int

Rules:
1. Default behavior version is 1
2. If meaning changes, create behavior version 2
3. Rebuild can target a behavior version for audit
4. Production runtime uses latest behavior version for new events only

Important:
Historical logs replayed under v1 must remain valid forever.

This is primarily for auditing and phased rollout, not for rewriting history.

---

## 7. Event Application Proof Hash

Optional but recommended for high critical projections:

For each applied canonical event:
Compute apply_proof_hash = hash(
  event_id,
  event_type,
  event_version,
  canonical_payload_hash,
  affected_projection_row_keys,
  resulting_row_hashes
)

Store in a lightweight audit table.

Purpose:
1. Debug semantic drift
2. Pinpoint first event where divergence happens

Must be deterministic.

---

## 8. CI Gates Additions

Gate E Domain Invariant Gate
1. Run invariant suite on fixtures
2. Run invariant suite on staging sample log
3. Fail if any invariant fails

Gate F Handler Semantics Gate
If projection handler code changes:
1. Require explicit declaration in PR metadata:
   behavior_change_intent = none | explicit_event_change
2. If explicit_event_change:
   require new event type or new event version and fixtures
3. If none:
   fingerprints and invariants must remain identical

---

## 9. PR Discipline

Any PR touching:
1. projection handlers
2. rebuild engine
3. event upcasters
4. migrations

Must include:
1. Statement: does this change domain behavior
2. If yes, which new event expresses it
3. Which invariants prove correctness

Silent behavior change is forbidden.

---

This document locks domain meaning over time by forcing behavior evolution to be explicit in the event model and verified by invariant tests.
