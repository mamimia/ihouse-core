# Phase 25 – OTA Modification Resolution Rules

Objective

Define deterministic adapter-side resolution rules for OTA modification events.

Background

Phase 24 introduced the intermediate semantic kind:

MODIFY

This allows the system to recognize OTA modification events without
forcing them into canonical booking lifecycle events too early.

However, semantic recognition alone is not enough.

A modification event must only be accepted if the adapter can determine,
from payload semantics alone, what canonical meaning the provider event has.

Problem

A provider event such as:

reservation_modified

may represent multiple meanings:

- metadata-only update
- booking update
- date change
- full replacement of reservation intent

Without deterministic resolution rules, accepting such events would
create ambiguity inside the canonical ingestion pipeline.

Phase 25 Goal

Phase 25 must define when a modification event may be accepted and when
it must be rejected.

Resolution Principle

A modification event may only be accepted if its meaning can be resolved
deterministically from payload semantics alone.

If deterministic resolution is not possible, the event must be rejected
at the adapter boundary.

Hard Constraints

Phase 25 must not introduce:

- booking_state lookup from the adapter layer
- duplicate detection in application code
- reconciliation queues
- buffering or pending-event storage
- canonical DB gate changes
- direct mutation of projections
- hidden fallback logic

Architectural Limits

The current OTA contract remains:

one normalized event  
→ one canonical envelope

Therefore Phase 25 must not pretend to support multi-envelope emission
unless the ingestion contract is explicitly changed in a future phase.

This means:

- single-envelope deterministic resolution may be allowed if payload
  semantics make it safe
- multi-envelope outcomes such as CANCEL + CREATE remain out of scope
  unless the canonical adapter contract is expanded in a later phase

Required Deliverables

Phase 25 must produce:

1. explicit deterministic resolution rules for Booking.com modification events
2. adapter-side rule implementation based only on payload semantics
3. deterministic rejection reasons for unresolved or ambiguous cases
4. documentation updates reflecting the exact supported resolution surface

Acceptance Rule

A modification event may enter canonical envelope creation only if the
adapter can prove a deterministic canonical interpretation from the raw payload.

Otherwise:

MODIFY
→ REJECT

Success Criteria

- no ambiguous modification event enters the canonical event model
- no CREATE fallback is used for unresolved modification events
- no read-side lookup is introduced
- deterministic rejection remains the default safety behavior
