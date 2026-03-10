# iHouse Core – Canonical Event Architecture


## Version

Phase 28 – OTA External Surface Canonicalization (Locked)  
Phase 69 – Amendment Support Added (MODIFY reclassified to BOOKING_AMENDED)

Last Updated  
Phase 210 – Documentation Audit


## Purpose

Define the single canonical event contract.

Define the allowed external business event surface.

Ensure the database gate remains the single authority
for booking identity, deduplication, and state mutation.


## Core Principle

The database gate (`apply_envelope`) is the single canonical authority
allowed to mutate system state.

All booking state is derived from events.

The application layer may validate and transform events but may not
bypass the database gate.


## Canonical Event Flow

External systems interact with the system through the OTA ingestion
boundary.

Event processing pipeline:

External OTA

↓ provider registry resolution

↓ adapter normalization

↓ structural validation

↓ semantic classification

↓ semantic validation

↓ canonical envelope creation

↓ canonical envelope validation

↓ event append

↓ database gate (`apply_envelope`)

↓ state projection (`booking_state`)


## OTA Semantic Layer

The OTA ingestion layer classifies normalized provider events into
deterministic semantic kinds before envelope creation.

Supported semantic kinds:

CREATE  
CANCEL  
MODIFY

Purpose:

Prevent ambiguous OTA payloads from entering the canonical event model.

Responsibilities:

- classify normalized OTA events into semantic kinds
- validate semantic consistency of OTA payloads
- deterministically reject invalid OTA events

Constraints:

- no booking_state lookup
- no duplicate detection
- no state mutation


## Canonical Authority Boundary


### Application Layer

Allowed:

- provider registry resolution
- payload normalization
- structural validation
- semantic classification
- semantic validation
- envelope construction

Not allowed:

- booking_state mutation
- booking identity decisions
- duplicate detection
- state reconciliation
- bypassing apply_envelope


### Database Gate

Responsible for:

- booking identity enforcement
- duplicate detection
- overlap rules
- state mutation
- projection events


## Deterministic Guarantees

The system guarantees:

- deterministic replay
- single source of truth for booking state
- canonical authority of the database gate

Application logic may reject events but may not create alternative
state mutation paths.


## OTA Integration Model

External OTA providers are treated as untrusted event sources.

All external payloads must pass through the OTA ingestion boundary.

The canonical event model is protected by:

- provider isolation
- normalization
- semantic validation
- canonical envelope validation
- database gate enforcement


## OTA Modification Semantics

OTA providers may emit modification events representing changes to
existing reservations rather than explicit lifecycle transitions.

Example:

reservation_modified


### Canonical Rule (Updated Phase 69)

MODIFY was originally rejected by default (Phase 28).

Since Phase 69, MODIFY payloads are reclassified to BOOKING_AMENDED.
This is a canonical booking lifecycle event representing date, rate,
or guest-count changes to an existing reservation.

Current invariant:

MODIFY → reclassified to BOOKING_AMENDED → processed through apply_envelope


### Adapter Behavior (Updated Phase 69)

When an OTA modification payload is received:

reservation_modified  
→ semantic classification MODIFY  
→ reclassified to BOOKING_AMENDED by adapter  
→ processed through apply_envelope

Adapters are required to:

- extract the changed fields (dates, rates, guest count)
- emit a BOOKING_AMENDED canonical envelope
- pass through apply_envelope like any other lifecycle event

Adapters are still not allowed to:

- split MODIFY into CANCEL + CREATE
- perform booking_state lookups during classification


## Multi-OTA Adapter Architecture

Phase 27 introduced a shared OTA ingestion pipeline and multi-provider
adapter registry.

Architectural result:

- service layer acts as entrypoint only
- shared pipeline performs orchestration
- provider adapters remain isolated
- new providers can be added without changing the canonical DB gate

The architecture was validated through:

- existing Booking.com adapter
- additional Expedia scaffold adapter used to prove provider
  extensibility through the shared pipeline

This does not mean all target OTA providers are fully implemented.

It means the architecture now supports multi-provider extension
without redesigning the deterministic ingestion boundary.


## Architectural Status

The following invariants are locked:

External event ingestion must remain deterministic.

Only canonical lifecycle outcomes may reach the database gate.

OTA modification events are reclassified to BOOKING_AMENDED (Phase 69).

The shared OTA pipeline must remain provider-agnostic.

Provider-specific logic must remain isolated inside provider adapters.


## Historical Transport Artifact

Prior to Phase 28 the OTA boundary emitted a generic transport envelope:

BOOKING_SYNC_INGEST

Phase 28 replaced this external surface with explicit lifecycle events:

BOOKING_CREATED  
BOOKING_CANCELED

Phase 69 added:

BOOKING_AMENDED

The BOOKING_SYNC_INGEST transport artifact has been fully removed
from the execution pipeline. It no longer appears in any code path.