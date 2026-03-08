# Phase 55 Spec — Agoda Adapter

## Objective

Add Agoda as the fourth full OTA provider adapter: BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED.

## Status

In Progress

## Background

Phase 54 completed Airbnb. The adapter pattern is fully proven:
- Interface: OTAAdapter (normalize + to_canonical_envelope)
- Amendment: extract_amendment_{provider}() + normalize_amendment() dispatch
- Registry: single line addition
- Tests: ~18 contract tests per provider

## Agoda Webhook Structure (canonical design)

Agoda event types:
- `booking.created`    → BOOKING_CREATED
- `booking.cancelled`  → BOOKING_CANCELED
- `booking.modified`   → BOOKING_AMENDED

Agoda amendment payload (under `modification`):
```json
{
  "modification": {
    "check_in_date":  "2026-10-01",
    "check_out_date": "2026-10-07",
    "num_guests":     2,
    "reason":         "date_change"
  }
}
```

Core fields (all events):
- `event_id`       — unique event identifier
- `booking_ref`    — Agoda booking reference (maps to reservation_id)
- `property_id`    — property identifier
- `occurred_at`    — ISO datetime string
- `event_type`     — semantic event type
- `tenant_id`      — iHouse tenant identifier

## Scope

1. `amendment_extractor.py` — add extract_amendment_agoda() + dispatch
2. `src/adapters/ota/agoda.py` — new file
3. `registry.py` — register AgodaAdapter
4. `semantics.py` — add Agoda event type aliases
5. `tests/test_agoda_contract.py` — ~18 contract tests

## Invariants — must not change

- apply_envelope is the only write authority
- No DB schema changes
- No canonical code changes
