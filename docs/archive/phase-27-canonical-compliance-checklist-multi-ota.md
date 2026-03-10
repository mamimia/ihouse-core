# Phase 27 – Canonical Compliance Checklist (Multi-OTA)

## Purpose

This checklist defines the canonical compliance rules for
implementing OTA provider adapters in the iHouse Core system.

Its purpose is to guarantee that multi-OTA integrations do not
violate the deterministic event architecture or the canonical
authority of the database gate.

This document is part of the canonical architecture governance
artifacts of the system.


## Architectural Context

External OTA providers are treated as untrusted event sources.

All external events must pass through the OTA ingestion boundary
before reaching the canonical database gate.

The database gate (`apply_envelope`) remains the only authority
allowed to mutate system state.

Adapters operate strictly in the application layer.


## Compliance Rules


### 1. Database Authority

Adapters must never bypass the canonical database gate.

All accepted events must pass through:

apply_envelope


### 2. No State Reads

Adapters must never read or depend on:

booking_state

Adapters must not perform historical reconciliation.


### 3. No State Mutation

Adapters must never mutate canonical state.

Adapters may only produce canonical envelopes.


### 4. Deterministic Event Surface

Adapters may only emit deterministic canonical lifecycle events.

Allowed canonical events:

BOOKING_CREATED  
BOOKING_CANCELED


### 5. Modification Rejection

OTA modification notifications must never be interpreted as
canonical lifecycle transitions.

The following rule is mandatory:

MODIFY → deterministic reject-by-default


### 6. No State Inference

Adapters must not infer lifecycle transitions from previous state.

Adapters must not:

- split MODIFY into CANCEL + CREATE
- generate UPDATE events
- attempt reconciliation logic


### 7. Provider Isolation

Each OTA provider must be implemented in an isolated adapter
module.

Provider semantics must not leak into the canonical event model.


### 8. Shared Pipeline Purity

The shared OTA ingestion pipeline must not contain provider-
specific business logic.

Provider-specific logic must exist only inside provider adapters.


### 9. Registry Responsibility

The provider registry must only resolve provider identifiers to
adapter implementations.

The registry must contain no business logic.


### 10. No External Snapshot Reconciliation

Adapters must not call OTA APIs to retrieve reservation snapshots
for reconciliation purposes.

State comparison and synchronization belong to a future layer:

OTA Sync Recovery Layer


## Compliance Verification

Phase 27 is considered compliant only if the following conditions
are true:

1. Multiple OTA providers can be added without modifying the
   canonical event model.

2. Adding a provider does not require changes to apply_envelope.

3. Adding a provider does not introduce provider-specific logic
   into the shared pipeline.

4. All adapters enforce deterministic rejection of MODIFY events.


## Architectural Guarantee

This checklist guarantees that multi-OTA integrations remain fully
compatible with the deterministic architecture of iHouse Core.
