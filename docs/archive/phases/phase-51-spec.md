# Phase 51 Spec — Python Pipeline Integration: BOOKING_AMENDED Routing

## Objective

Wire BOOKING_AMENDED through the Python OTA adapter pipeline so that
`reservation_modified` OTA events reach `apply_envelope` as canonical `BOOKING_AMENDED` events,
instead of being deterministically rejected as `MODIFY`.

## Status

In Progress

## Background

Phase 50 delivered `apply_envelope` with a full `BOOKING_AMENDED` branch — live on Supabase, E2E verified.

The Python pipeline does not yet route `BOOKING_AMENDED` through. Currently:

```
reservation_modified → semantics.py → MODIFY → reject (ValueError)
```

After this phase:

```
reservation_modified → semantics.py → BOOKING_AMENDED → pipeline → apply_envelope → APPLIED
```

## Scope

### In scope

1. `src/adapters/ota/semantics.py`
   - Add `BOOKING_AMENDED` semantic kind
   - Map `reservation_modified` → `BOOKING_AMENDED`

2. `src/adapters/ota/pipeline.py` (or `validator.py`)
   - Allow `BOOKING_AMENDED` through to `to_canonical_envelope`
   - (Currently MODIFY is rejected before envelope construction)

3. `src/adapters/ota/bookingcom.py`
   - `to_canonical_envelope`: handle `BOOKING_AMENDED` — build canonical envelope using AmendmentFields

4. `src/adapters/ota/service.py`
   - `ingest_provider_event_with_dlq` must allow BOOKING_AMENDED to flow like CREATED/CANCELED

5. `tests/test_booking_amended_contract.py`
   - Full pipeline tests: `reservation_modified` → BOOKING_AMENDED → APPLIED on live Supabase
   - Unit contract tests for semantics, envelope shape, validator

### Out of scope

- Expedia adapter full BOOKING_AMENDED routing (Expedia is scaffold only)
- BOOKING_AMENDED idempotency collision tests (Phase 52 candidate)
- UI / webhook layer

## Invariants — must not change

- `apply_envelope` remains single write authority
- `event_log` remains append-only
- `booking_state` remains projection-only
- No adapter reads `booking_state`
- `booking_id = "{source}_{reservation_ref}"` — deterministic

## Expected test count

158 passing now → target ~175+ after Phase 51
