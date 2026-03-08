# iHouse Core — Work Context

## Current Active Phase

Phase 47 — OTA Payload Boundary Validation

## Last Closed Phase

Phase 46 — System Health Check

## Current Objective

Every production-grade API (Stripe, Twilio, Airbnb) validates inputs at the boundary before they touch the canonical system. Currently, malformed OTA payloads (missing reservation_id, invalid occurred_at, unknown provider) flow silently into the pipeline and fail deep inside normalize() or apply_envelope.

Phase 47 introduces an explicit, structured validation layer at the OTA boundary.

This is different from the existing `validator.py` (which validates semantic ClassifiedBookingEvent kinds). This validates the **raw incoming webhook payload** before normalization.

## Why This Is the Right Next Step

1. Without boundary validation, any malformed payload can corrupt the pipeline silently
2. This is a prerequisite for BOOKING_AMENDED — amendment payloads must be validated
3. Stripe validates every webhook at the boundary before processing
4. It creates an explicit contract between OTA providers and the system

## Scope

### `src/adapters/ota/payload_validator.py`

```python
@dataclass(frozen=True)
class PayloadValidationResult:
    valid: bool
    errors: list[str]
    provider: str
    event_type_raw: str | None

def validate_ota_payload(provider: str, payload: dict) -> PayloadValidationResult
```

#### Rules validated:

| Rule | Error |
|------|-------|
| provider must be non-empty string | PROVIDER_REQUIRED |
| payload must be a dict | PAYLOAD_MUST_BE_DICT |
| reservation_id must be present and non-empty | RESERVATION_ID_REQUIRED |
| tenant_id must be present and non-empty | TENANT_ID_REQUIRED |
| occurred_at must be present and parseable as ISO datetime | OCCURRED_AT_INVALID |
| event_type/type/action must be present | EVENT_TYPE_REQUIRED |

#### Integration:

Called at the top of `process_ota_event` in `pipeline.py`, before `normalize()`.
If validation fails → raise `ValueError(f"OTA payload validation failed: {errors}")`.

#### Contract tests:
- valid payload → valid=True, errors=[]
- missing reservation_id → valid=False, RESERVATION_ID_REQUIRED in errors
- missing tenant_id → valid=False
- invalid occurred_at → valid=False, OCCURRED_AT_INVALID
- missing event_type → valid=False, EVENT_TYPE_REQUIRED
- empty provider → valid=False, PROVIDER_REQUIRED
- multiple errors collected at once (not fail-fast)
- pipeline.py raises on invalid payload

Out of scope:
- provider-specific field validation (Booking.com vs Expedia)
- payload signature verification (separate phase)
