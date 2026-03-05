# iHouse Core – System Truth

## Canonical Write Path

All writes to the system must go through:

apply_envelope()

This RPC function is the single write gate of the system.

## Canonical Ledger

public.event_log

This table is the canonical ledger of the system.
Every accepted envelope is appended here.

## Read Model

public.booking_state

This table is a projection (derived read model).
It must never be treated as a source of truth.

## Registry Tables

public.event_kind_registry  
public.event_kind_versions

These tables define which events are valid and which versions are supported.

## Deterministic Rule

The system must always be rebuildable by replaying event_log.

event_log → apply → booking_state
