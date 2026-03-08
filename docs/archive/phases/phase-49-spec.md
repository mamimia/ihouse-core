# Phase 49 Spec — Normalized AmendmentPayload Schema

## Objective

Define a canonical, provider-agnostic amendment payload schema so that `apply_envelope`'s
BOOKING_AMENDED branch (Phase 50) can receive a normalized input regardless of which OTA
provider originated the amendment.

## Rationale

Booking.com puts amendment data in `new_reservation_info`; Expedia puts it in
`changes.dates` / `changes.guests`. Phase 50 cannot know about provider-specific shapes.
A normalized schema is required before `apply_envelope` can be extended.

## Deliverables

### Modified: `src/adapters/ota/schemas.py`

**New dataclass:**
```python
@dataclass(frozen=True)
class AmendmentFields:
    new_check_in: Optional[str]       # ISO date string or None
    new_check_out: Optional[str]      # ISO date string or None
    new_guest_count: Optional[int]    # integer or None
    amendment_reason: Optional[str]   # provider note or None
```

### New file: `src/adapters/ota/amendment_extractor.py`

**Functions:**
- `extract_amendment_bookingcom(payload) → AmendmentFields`
  - Reads from `new_reservation_info` block
- `extract_amendment_expedia(payload) → AmendmentFields`
  - Reads from `changes.dates` and `changes.guests`
- `normalize_amendment(provider, payload) → AmendmentFields`
  - Dispatcher: routes to correct extractor by provider name (case-insensitive)
  - Raises `ValueError` on unknown provider

**Helpers:** `_nonempty(val) → str | None`, `_int_or_none(val) → int | None`

## Tests

15 contract tests:
- `AmendmentFields` is frozen (immutable)
- Booking.com extractor — all 4 fields
- Booking.com extractor — missing fields → None
- Expedia extractor — dates from `changes.dates`
- Expedia extractor — guests from `changes.guests`
- Expedia extractor — missing fields → None
- Unknown provider raises `ValueError`
- Dispatcher case-insensitive (`bookingcom`, `BookingCom`, `BOOKINGCOM`)
- Return type is `AmendmentFields`
- Integer coercion for `new_guest_count`

## Outcome

153 tests pass.
BOOKING_AMENDED prerequisites: 7/10 satisfied (AmendmentPayload ✅ added).

## Next Phase

Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch
