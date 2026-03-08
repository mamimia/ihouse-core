# iHouse Core — Work Context

## Current Active Phase

Phase 48 — Idempotency Key Standardization

## Last Closed Phase

Phase 47 — OTA Payload Boundary Validation

## Current Objective

Stripe's idempotency model is one of the most studied in the industry. Their keys are:
- Namespaced (no cross-provider collision)
- Deterministic (same input → same key, always)
- Validated before use

Currently, iHouse Core uses `external_event_id` directly as the idempotency key in both adapters. This is fragile:
- Two providers can emit the same `event_id` string for different events
- Booking.com `ev_001` and Expedia `ev_001` would collide
- `event_id` from Booking.com is raw from the webhook — no namespace, no type disambiguation

Phase 48 standardizes idempotency keys across all OTA adapters.

## Scope

### `src/adapters/ota/idempotency.py`

```python
def generate_idempotency_key(provider: str, event_id: str, event_type: str) -> str
    # Format: "{provider}:{event_type}:{event_id}" (lowercase, colon-separated)
    # Example: "bookingcom:booking_created:ev_001"

def validate_idempotency_key(key: str) -> bool
    # Returns True if key matches "{string}:{string}:{string}" pattern
    # Returns False for empty, None, or wrong format
```

### Update adapters:

- `bookingcom.py` → `to_canonical_envelope()` → use `generate_idempotency_key(...)` instead of `external_event_id`
- `expedia.py` → same

### Contract tests:
- known input → expected key format
- different providers → different keys
- same event_id on two providers → different keys (no collision)
- same event_id, different event_type → different keys
- validate_idempotency_key accepts valid, rejects empty/malformed
- adapters emit correct key format after update

Out of scope:
- idempotency key TTL/expiry
- response caching
- cross-phase dedup check at Python layer (apply_envelope already handles this at DB level)
