# Phase 56 Spec — Trip.com Adapter

## Objective

Add Trip.com as the fifth full OTA provider adapter.

## Status

In Progress

## Trip.com Webhook Structure

Event types:
- `order_created`   → BOOKING_CREATED
- `order_cancelled` → BOOKING_CANCELED
- `order_modified`  → BOOKING_AMENDED

Amendment payload (under `changes`):
```json
{
  "changes": {
    "check_in":  "2026-10-01",
    "check_out": "2026-10-07",
    "guests":    2,
    "remark":    "date_adjustment"
  }
}
```

Core fields:
- `event_id`    — unique event identifier
- `order_id`    — Trip.com booking reference (→ reservation_id)
- `hotel_id`    — property identifier (→ property_id)
- `occurred_at` — ISO datetime
- `event_type`  — semantic event type
- `tenant_id`   — iHouse tenant

## Scope

1. amendment_extractor.py — extract_amendment_tripcom()
2. src/adapters/ota/tripcom.py — new adapter
3. registry.py — register TripComAdapter
4. semantics.py — order_created / order_cancelled / order_modified
5. tests/test_tripcom_contract.py

## Invariants — must not change

- apply_envelope single write authority
- No canonical changes
- No DB changes
