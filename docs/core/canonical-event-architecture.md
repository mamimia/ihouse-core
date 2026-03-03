# iHouse Core – Canonical Event Architecture

## Status
Authoritative

Last closed:
Phase 17A – Operational Runner, Secrets, CI, and Smoke Hardening

Current:
Phase 17B – Canonical Governance Completion

## Purpose
Define the single allowed external business event surface.
Define the single canonical persistence contract.
Define the single canonical operational apply path.

## Canonical Business Event Types
BOOKING_CREATED
BOOKING_UPDATED
BOOKING_CANCELED
BOOKING_CHECKED_IN
BOOKING_CHECKED_OUT
BOOKING_SYNC_ERROR
AVAILABILITY_UPDATED
RATE_UPDATED

No additional external event types are allowed without registry update and validation.

## External Event Sources
Any external producer must emit canonical business events only.
This includes user self-booking and manual bookings.
All external sources must flow through the canonical Supabase apply gate.

## Internal Events
Internal events may exist as implementation detail.
They are never accepted from the public API.

## External Envelope Contract
An external envelope must contain:
type
payload
idempotency.request_id

The system derives:
envelope_id from idempotency.request_id

## Enforcement Rules
Unknown external type is rejected.
Every allowed type must map to a handler via registry.
No handler may exist without a canonical mapping.
Event types must be SCREAMING_SNAKE_CASE.
Idempotency must be enforced before accepting duplicate application.

## Supabase Authority
Supabase public.event_log is the single canonical event store.
All rebuild and replay derive exclusively from this table.
SQLite is forbidden as a production write path.

## Idempotency Gate
apply_envelope is the canonical atomic write gate.
It writes envelope_received once per envelope_id.
It prevents duplicate application by returning ALREADY_APPLIED.

## Determinism Requirement
Given the same ordered canonical event log, state must be identical across runs.
