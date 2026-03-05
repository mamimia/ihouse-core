# iHouse Core — Live System

This document describes the current technical architecture of the running system.

## Core Architecture

The system follows an event sourced architecture.

Core principles:

- event_log is the canonical ledger of all system events
- apply_envelope is the only allowed write gate
- projections derive read models from the ledger
- the system must support deterministic rebuild from the event log

## Write Path

External sources send envelopes.

The envelope enters the system through:

Supabase RPC  
apply_envelope

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

## Future Evolution

Additional projections and domain modules may be added without breaking the canonical ledger model.
