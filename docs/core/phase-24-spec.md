# Phase 24 – OTA Modification Semantics

Objective

Introduce deterministic handling for OTA modification events.

Background

Certain OTA providers emit events that represent changes to existing
reservations rather than explicit create or cancel events.

Example:

Booking.com
reservation_modified

Problem

These events may represent different semantic meanings depending on
the payload.

Possible meanings

- metadata change
- booking update
- date change requiring cancel + recreate

Scope

Phase 24 introduces explicit semantic classification for modification events.

New semantic kind

MODIFY

Adapter responsibility

Adapters must deterministically map modification events into one of:

UPDATE
CANCEL + CREATE
REJECT

Constraints

Phase 24 must not introduce read-side booking lookup.

The adapter must decide based solely on payload semantics.

Completion Criteria

Booking.com adapter explicitly handles reservation_modified events.

Semantic mapping rules are deterministic.

Modification events cannot silently fall back to CREATE.

