# Phase 27 – Multi-OTA Adapter Architecture

## Status

Active Phase

Last Closed Phase  
Phase 26 – OTA Provider Verification


## Objective

Introduce a scalable architecture for integrating multiple OTA
providers with the canonical ingestion pipeline while preserving
the deterministic event model.

The architecture must allow multiple external providers to submit
events without leaking provider-specific semantics into the
canonical event system.


## Architectural Context

External OTA providers are treated as untrusted event sources.

All external booking events must pass through the OTA ingestion
boundary before reaching the canonical database gate.

The canonical event authority remains unchanged:

apply_envelope is the only authority allowed to mutate state.

booking_state remains projection-only.


## External Provider Targets

Initial providers supported by the architecture:

Booking.com  
Expedia  
Airbnb  
Agoda  
Trip.com


## Supported External Events

Only deterministic lifecycle events are accepted by the canonical model.

Accepted canonical lifecycle events:

BOOKING_CREATED  
BOOKING_CANCELED

OTA modification notifications are classified as:

MODIFY

Canonical rule (locked in Phase 25 and verified in Phase 26):

MODIFY → deterministic reject-by-default


## Multi-Provider Adapter Architecture

Phase 27 introduces a structured adapter architecture composed of
four layers.

Raw Provider Event

↓ provider adapter normalization

↓ semantic classification

↓ semantic validation

↓ canonical envelope creation

↓ canonical envelope validation

↓ database gate (apply_envelope)


## Adapter Isolation Principle

Each OTA provider must be implemented as an isolated adapter module.

Provider-specific semantics must never leak into the canonical
event model.

Adapters may only perform:

- payload normalization
- structural validation
- semantic classification
- canonical envelope construction

Adapters are not allowed to:

- read booking_state
- reconcile booking history
- infer lifecycle transitions from past state
- mutate canonical state
- bypass apply_envelope


## Shared OTA Pipeline

The ingestion boundary provides a shared processing pipeline used
by all adapters.

The shared pipeline performs the following steps:

1. provider resolution
2. adapter normalization
3. semantic classification
4. semantic validation
5. canonical envelope creation
6. canonical envelope validation
7. submission to apply_envelope


## Provider Adapter Contract

Each provider adapter must implement the same logical contract.

Responsibilities:

normalize(provider_payload)

Transform provider-specific payloads into a normalized internal
representation.

classify(normalized_event)

Classify the semantic meaning of the event.

Allowed semantic kinds:

CREATE  
CANCEL  
MODIFY

validate(normalized_event, semantic_kind)

Verify payload structure and semantic consistency.

to_canonical_envelope(normalized_event, semantic_kind)

Construct canonical envelope inputs when semantic kind is
deterministic.

CREATE → BOOKING_CREATED  
CANCEL → BOOKING_CANCELED

MODIFY → deterministic rejection


## Provider Registry

A provider registry maps provider identifiers to their
corresponding adapter implementations.

Example mapping:

booking_com → BookingComAdapter  
expedia → ExpediaAdapter  
airbnb → AirbnbAdapter  
agoda → AgodaAdapter  
trip_com → TripComAdapter

The registry performs provider resolution but contains no business
logic.


## Provider Adapter Isolation

Each provider must be implemented in an isolated module.

Example structure:

src/adapters/ota/providers/

booking_com/
adapter.py
normalizer.py
mapper.py

expedia/
adapter.py
normalizer.py
mapper.py

airbnb/
adapter.py
normalizer.py
mapper.py

agoda/
adapter.py
normalizer.py
mapper.py

trip_com/
adapter.py
normalizer.py
mapper.py


## Deterministic Rejection of MODIFY

OTA providers often emit modification notifications representing
changes to existing reservations.

Because these payloads require external state comparison, they
cannot be deterministically interpreted.

Therefore the ingestion layer enforces the canonical rule:

MODIFY → deterministic reject-by-default

Adapters must not attempt to:

- infer UPDATE semantics
- split MODIFY into CANCEL + CREATE
- fetch reservation snapshots from OTA APIs
- compare payloads with internal booking state


## Architectural Guarantee

Phase 27 guarantees that:

- multiple OTA providers can integrate without altering the
  canonical event model

- provider semantics remain isolated from the canonical system

- all accepted events remain deterministic

- the canonical database gate remains the only authority allowed
  to mutate state


## Out of Scope

The following capabilities are explicitly out of scope for Phase 27.

OTA synchronization engines

OTA snapshot reconciliation

state comparison recovery logic

These capabilities may be introduced in a future layer:

OTA Sync Recovery Layer


## Phase Completion Conditions

Phase 27 is considered complete when:

1. A shared multi-provider OTA adapter architecture exists.

2. Provider adapters are isolated and follow a common contract.

3. Multiple OTA providers can normalize payloads into canonical
events.

4. Only deterministic lifecycle events are accepted.

5. OTA modification events remain rejected.

6. The canonical database gate remains unchanged.


## Architectural Result

The system now supports scalable OTA integration while preserving
the deterministic integrity of the canonical event model.
