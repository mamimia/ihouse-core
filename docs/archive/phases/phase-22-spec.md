
# iHouse Core — Phase 22 Spec

## Phase
Phase 22 — External Ingestion Hardening

## Objective
Implement a minimal OTA ingestion adapter layer that accepts external channel payloads, normalizes them into canonical external envelopes, validates them, and submits them exclusively through apply_envelope.

No new write path may be introduced.

## Canonical Constraints

1. event_log remains the only source of truth.
2. booking_state remains a projection only.
3. apply_envelope remains the only allowed write gate.
4. External systems must never write directly to event_log or booking_state.
5. Replay safety must remain preserved.

## Phase Scope

This phase implements only the minimal OTA ingestion boundary.

Supported channels in the first implementation:
bookingcom only

Supported canonical business events:
BOOKING_CREATED
BOOKING_CANCELED

All other OTA event types must be rejected.

## Required Boundary Separation

The implementation must preserve three separate boundaries:

HTTP boundary  
Receives request, authenticates, resolves channel, returns deterministic response.

Channel normalization boundary  
Maps raw OTA payload into an internal normalized structure.

Canonical apply boundary  
Builds canonical external envelope input and submits it to apply_envelope.

Do not mix channel-specific logic into the canonical apply layer.

## Canonical External Envelope Input

The only external envelope shape submitted to apply_envelope is:

type  
payload  
idempotency.request_id

## Internal Normalization Rule

Even though the canonical envelope is small, the adapter must first normalize raw OTA payload into an internal normalized object.

Flow:

Raw OTA payload  
→ internal normalized object  
→ canonical external envelope input  
→ apply_envelope

This prevents OTA-specific payload quirks from leaking into the canonical contract.

## Authority Rules

tenant_id must come from authentication or server-side mapping.  
source must come from the route path parameter.  
Request body may provide reservation data only.  
Request body must never be treated as authority for tenant or source.

## Canonical Payload Requirements

For BOOKING_CREATED and BOOKING_CANCELED, canonical payload must include at least:

tenant_id  
source  
reservation_ref  
property_id  

For BOOKING_CREATED payload must also include:

check_in  
check_out

## Idempotency Rule

idempotency.request_id must be stable and deterministic.

It must be derived from stable source fields only.

Do not derive request_id from:
random UUID  
received_at  
runtime timestamp  
mutable transport metadata

## Deterministic Response Classification

API responses must classify outcomes deterministically as:

APPLIED  
DUPLICATE  
REJECTED

The HTTP layer may choose response codes, but business outcome classification must remain stable for identical input.

## Minimal File Blueprint

Recommended structure:

src/adapters/ota/
  base.py
  bookingcom.py
  registry.py
  schemas.py
  validator.py
  service.py

Responsibility split:

base.py  
Defines adapter interface.

bookingcom.py  
Maps Booking.com payloads into internal normalized structure and canonical envelope input.

registry.py  
Maps channel name to adapter implementation.

schemas.py  
Defines internal normalized types and canonical external envelope input model.

validator.py  
Validates canonical envelope before calling apply_envelope.

service.py  
Coordinates authentication context, adapter resolution, normalization, validation, call to apply_envelope, and deterministic response mapping.

## Minimal Endpoint

POST /v1/ingest/ota/{channel}

Responsibilities:
authenticate request  
derive tenant context  
resolve channel adapter  
normalize payload  
validate canonical envelope  
call apply_envelope  
return deterministic result

## First Implementation Rule

Do not build a multi-provider framework first.

Start with:
one endpoint  
one adapter  
one validator  
one service

Only bookingcom should be implemented first.

## Explicit Non-Goals

This phase must not:

add staging tables  
write directly to event_log  
write directly to booking_state  
accept STATE_UPSERT  
create internal projection events in application code  
implement replay tooling  
implement out-of-order reconciliation  
support unsupported OTA event approximations

## Exit Criteria

Phase 22 is complete when:

1. POST /v1/ingest/ota/bookingcom exists
2. Booking.com payloads can be normalized into canonical external envelopes
3. only BOOKING_CREATED and BOOKING_CANCELED are accepted
4. requests are submitted only through apply_envelope
5. responses are deterministically classified as APPLIED, DUPLICATE, or REJECTED
6. no new persistence path is introduced

