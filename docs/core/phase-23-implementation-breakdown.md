# Phase 23 — Minimal Implementation Breakdown

## Scope

Phase 23 adds semantic pre-gate hardening inside the OTA adapter boundary only.

It does not:
- add a new write path
- add a new persistence table
- add read-side booking lookups
- perform duplicate booking detection in application code
- modify apply_envelope behavior
- introduce buffering or reconciliation
- widen external supported kinds beyond the active surface

## Canonical Intent

The OTA adapter layer must classify provider events into explicit semantic meaning
before canonical envelope creation.

The database apply gate remains the only authority for canonical business identity,
state mutation, and duplicate booking enforcement.

## Minimal Responsibilities

1. Explicit semantic classification of normalized OTA events
2. Semantic self-consistency validation
3. Deterministic semantic rejection codes for invalid OTA payloads

## Active Semantic Surface

Current active external semantic surface:
- CREATE
- CANCEL

This phase does not introduce external UPDATE handling.

## Classification Inputs

Classification must use the normalized OTA event structure, especially:
- raw_event_name
- provider_payload.status

The classification must be deterministic.

## Classification Rules

Booking.com mapping:
- reservation_created -> CREATE
- reservation_cancelled -> CANCEL
- status=confirmed -> CREATE
- status=cancelled -> CANCEL

If raw_event_name and provider status disagree, reject deterministically.

## Semantic Validation Rules

CREATE must:
- classify as CREATE
- contain check_in
- contain check_out
- use provider semantics consistent with creation

CANCEL must:
- classify as CANCEL
- use provider semantics consistent with cancellation

No read-side booking lookup is allowed in this phase.

## Deterministic Rejection Codes

- UNSUPPORTED_PROVIDER_EVENT
- CONFLICTING_PROVIDER_SEMANTICS
- INVALID_CREATE_EVENT
- INVALID_CANCEL_EVENT
- UNKNOWN_SEMANTIC_KIND
