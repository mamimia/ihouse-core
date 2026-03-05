# iHouse Core – Database Structure

## Canonical Ledger

table: public.event_log

Purpose:
append-only ledger of all accepted events.

Important columns:
- envelope_id
- event_kind
- event_version
- payload
- created_at


## Read Model

table: public.booking_state

Purpose:
projection built from event_log.

Important fields:
- booking_id
- property_id
- check_in
- check_out
- status


## Event Registry

table: public.event_kind_registry

Purpose:
defines allowed event kinds.


table: public.event_kind_versions

Purpose:
defines supported versions per event.


## Canonical Write Gate

function: public.apply_envelope()

Responsibilities:
- validate envelope
- check registry
- append to event_log
- update booking_state
