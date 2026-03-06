# iHouse Core – Canonical Event Architecture


## Version

Phase 24 – OTA Modification Semantics

Last Closed Phase  
Phase 23 – External Event Semantics Hardening


## Purpose

Define the single canonical event contract.

Define the signal allowed external business event surface.

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

↓ adapter normalization

↓ structural validation

↓ semantic classification         (added in Phase 23)

↓ semantic validation             (added in Phase 23)

↓ canonical envelope creation

↓ canonical envelope validation

↓ event append

↓ database gate (`apply_envelope`)

↓ state projection (`booking_state`)


## OTA Semantic Layer (Phase 23)

Phase 23 introduced a semantic classification layer for OTA events.

Purpose

Prevent ambiguous OTA payloads from entering the canonical event model.

Responsibilities

- classify normalized OTA events into semantic kinds
- validate semantic consistency of OTA payloads
- deterministically reject invalid OTA events

Constraints

- no booking_state lookup
- no duplicate detection
- no state mutation


## Canonical Authority Boundary

Application Layer

Allowed:

- payload normalization
- structural validation
- semantic classification
- envelope construction

Not allowed:

- booking_state mutation
- booking identity decisions
- duplicate detection


Database Gate

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

- normalization
- semantic validation
- canonical envelope validation
- database gate enforcement

