# Phase 54 Spec — Airbnb Adapter

## Objective

Add a full Airbnb OTA adapter: BOOKING_CREATED, BOOKING_CANCELED, BOOKING_AMENDED.
Register it in the pipeline so Airbnb webhooks flow through the exact same canonical path.

## Status

In Progress

## Background

Phase 53 completed Expedia to full parity with Booking.com.
Phase 54 adds the third provider: Airbnb.

The adapter pattern is fully proven. Adding Airbnb requires:
1. New file: `src/adapters/ota/airbnb.py`
2. Add `extract_amendment_airbnb()` to `amendment_extractor.py`
3. Register in `registry.py`
4. Payload validator entry in `payload_validator.py`
5. Contract tests: `tests/test_airbnb_contract.py`

## Airbnb Webhook Structure (canonical design)

Airbnb event types:
- `reservation_create`  → BOOKING_CREATED
- `reservation_cancel`  → BOOKING_CANCELED
- `alteration_create`   → BOOKING_AMENDED

Airbnb amendment payload (under `alteration`):
```json
{
  "alteration": {
    "new_check_in":  "2026-10-01",
    "new_check_out": "2026-10-07",
    "guest_count":   2,
    "reason":        "guest_request"
  }
}
```

Core fields (all events):
- `event_id`       — unique event identifier
- `reservation_id` — Airbnb booking reference
- `listing_id`     — maps to `property_id`
- `occurred_at`    — ISO datetime string
- `event_type`     — semantic event type
- `tenant_id`      — iHouse tenant identifier

## Scope

### In scope

1. `src/adapters/ota/amendment_extractor.py` — read fully before editing
   - Add `extract_amendment_airbnb()` reading `alteration.new_check_in/out/guest_count/reason`
   - Add `"airbnb"` to `_SUPPORTED_PROVIDERS`
   - Add dispatch in `normalize_amendment()`

2. `src/adapters/ota/airbnb.py` — new file
   - `normalize()`: maps `listing_id` → `property_id`
   - `to_canonical_envelope()`: CREATE / CANCEL / BOOKING_AMENDED branches

3. `src/adapters/ota/registry.py` — read fully before editing
   - Register `AirbnbAdapter`

4. `src/adapters/ota/payload_validator.py` — read fully before editing
   - Add Airbnb validation rule

5. `tests/test_airbnb_contract.py`
   - normalize, CREATE, CANCEL, AMENDED, cross-provider isolation

### Out of scope

- Live Airbnb webhook testing
- Airbnb OAuth / API key verification
- Any canonical code changes

## Invariants — must not change

- apply_envelope is the only write authority
- No DB schema changes
- no adapter reads booking_state
