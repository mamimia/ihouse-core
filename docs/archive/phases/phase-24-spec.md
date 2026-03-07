# Phase 24 – OTA Modification Semantics

Objective

Introduce explicit semantic recognition for OTA modification events
while preserving the deterministic event ingestion pipeline.

Background

Certain OTA providers emit events that represent changes to existing
reservations rather than explicit create or cancel events.

Example:

Booking.com
reservation_modified

Problem

These events may represent different semantic meanings depending on
payload semantics.

Possible meanings

- metadata change
- booking update
- date change requiring cancel + recreate

Scope

Phase 24 introduces explicit semantic classification for modification events.

New semantic kind

MODIFY

Phase 24 Behavior

OTA modification events may now be recognized as an intermediate semantic class.

This semantic class does not itself represent a canonical booking lifecycle event.

The semantic layer classifies modification events as `MODIFY`
without forcing them into CREATE or CANCEL semantics.

Architectural Rule

In the current Phase 24 implementation target, Booking.com modification
events that cannot be resolved deterministically from payload semantics
must be rejected at the adapter boundary.

Constraints

Phase 24 must not introduce:

- read-side booking lookup
- duplicate detection in application code
- mutation of booking_state outside the DB gate
- implicit fallback of modification events into CREATE
- non-deterministic provider interpretation

Completion Criteria

- Booking.com adapter explicitly recognizes `reservation_modified`
- OTA semantic layer supports `MODIFY`
- modification events do not silently fall back into CREATE or CANCEL
- unresolved modification events are rejected deterministically
