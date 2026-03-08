# iHouse Core — Work Context

## Current Active Phase

Phase 49 — Normalized AmendmentPayload Schema

## Last Closed Phase

Phase 48 — Idempotency Key Standardization

## Current Objective

Before adding BOOKING_AMENDED to apply_envelope (Phase 50), we need a canonical, provider-agnostic amendment payload structure. Currently, Booking.com puts amendment data in `new_reservation_info`, Expedia puts it in `changes.dates`. Phase 50 cannot know about provider-specific shapes.

Phase 49 defines the normalized schema and builds extractor functions for each provider.

This is a Python-only phase. No DDL changes.

## Scope

### `src/adapters/ota/schemas.py` — add `AmendmentFields`:

```python
@dataclass(frozen=True)
class AmendmentFields:
    new_check_in: str | None      # ISO date string or None
    new_check_out: str | None
    new_guest_count: int | None
    amendment_reason: str | None  # optional provider note
```

### `src/adapters/ota/amendment_extractor.py`:

```python
def extract_amendment_bookingcom(provider_payload: dict) -> AmendmentFields
def extract_amendment_expedia(provider_payload: dict) -> AmendmentFields
def normalize_amendment(provider: str, payload: dict) -> AmendmentFields
    # dispatches to the correct extractor by provider
    # raises ValueError for unknown provider
```

### Contract tests:
- Booking.com payload with new_reservation_info → correct AmendmentFields
- Expedia payload with changes.dates → correct AmendmentFields
- Missing fields → None (not raised — fields are optional)
- Unknown provider → ValueError
- AmendmentFields is frozen dataclass
- normalize_amendment dispatches correctly

Out of scope:
- DDL changes
- apply_envelope modifications (Phase 50)
- BOOKING_AMENDED in event_kind enum (Phase 50)
