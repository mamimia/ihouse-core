# iHouse Core — Live System

This document describes the current technical architecture of the
running system.

## Core Architecture

The system follows an event sourced architecture.

Core principles:

- event_log is the canonical ledger of all system events
- apply_envelope is the only allowed write gate
- projections derive read models from the ledger
- the system must support deterministic rebuild from the event log

## Write Path

External OTA sources enter the system through a layered canonical path:

OTA service entry  
→ shared OTA pipeline  
→ canonical envelope  
→ IngestAPI.ingest  
→ CoreExecutor.execute  
→ Supabase RPC  
→ apply_envelope

The OTA service entry is thin.

It accepts provider-facing inputs and delegates shared processing.

The shared OTA pipeline performs:

- provider registry resolution
- adapter normalization
- structural validation
- semantic classification
- semantic validation
- canonical envelope construction
- canonical envelope validation

The canonical external OTA events are:

- BOOKING_CREATED
- BOOKING_CANCELED

OTA modification notifications are classified as:

MODIFY  
→ deterministic reject-by-default

The canonical ingest API is the bridge from envelope construction into
core execution.

CoreExecutor is the single execution boundary for canonical envelopes.

OTA code does not call apply_envelope directly.

The replay harness verifies the OTA path through the same canonical
execution boundary without introducing a second write path.

The RPC validates:

- event_version
- event_kind
- emitted events

If valid:

1. envelope is recorded in event_log
2. projections update booking_state

## Read Path

Reads do not query the ledger directly.

Reads use projections.

Primary projection:

public.booking_state

## Safety Guarantees

- idempotent envelope processing
- deterministic state rebuild
- strict event validation
- single canonical write gate
- provider semantics isolated from core state mutation
- replay verification through the same OTA ingress contract
- no adapter-level state mutation
- no booking_state reads inside OTA adapters

## Current OTA Adapter Status

Implemented:
- Booking.com
- Expedia scaffold for architectural validation

Not yet implemented:
- Airbnb
- Agoda
- Trip.com

## Future Evolution

Additional adapters, projections, and domain modules may be added
without breaking the canonical ledger model.

Future OTA expansion must preserve the explicit boundary between OTA
entry, envelope construction, core ingest, and canonical execution.
