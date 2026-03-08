# Phase 48 Spec — Idempotency Key Standardization

## Objective

Standardize all OTA idempotency keys to a namespaced, collision-safe, deterministic format
inspired by Stripe's idempotency key design.

## Rationale

Previously, both adapters (Booking.com, Expedia) set `idempotency_key = raw external_event_id`
from the OTA provider. Two providers could emit the same event_id for different events,
causing cross-provider key collisions. Cross-event-type collisions were also possible.

## Deliverables

### New file: `src/adapters/ota/idempotency.py`

**Functions:**
- `generate_idempotency_key(provider, event_id, event_type) → str`
  - Format: `"{provider}:{event_type}:{event_id}"` (all lowercase, colons in values sanitized)
  - Deterministic — same inputs always produce same key
  - Raises on empty inputs
- `validate_idempotency_key(key) → bool`
  - Returns True only for keys with exactly 3 colon-separated segments

### Modified:
- `src/adapters/ota/bookingcom.py` — uses `generate_idempotency_key`
- `src/adapters/ota/expedia.py` — uses `generate_idempotency_key`

### Updated tests:
- `tests/test_ota_replay_harness.py` — updated for new key format
- `tests/test_ota_pipeline_contract.py` — updated for new key format

## Tests

19 contract tests:
- Format validation
- Cross-provider uniqueness (`bookingcom:created:X` ≠ `expedia:created:X`)
- Cross-type uniqueness (`bookingcom:created:X` ≠ `bookingcom:canceled:X`)
- Lowercase coercion
- Colon sanitization in values
- Empty inputs raise
- validate_idempotency_key: valid/invalid patterns
- Adapter integration

## Outcome

138 tests pass (2 pre-existing SQLite failures unrelated).
Cross-provider and cross-type key collisions are impossible.
Key format ready for `BOOKING_AMENDED` events when implemented.
