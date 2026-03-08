# iHouse Core — Work Context

## Current Active Phase

Phase 51 — Python Pipeline Integration (BOOKING_AMENDED routing)

## Last Closed Phase

Phase 50 — BOOKING_AMENDED DDL + apply_envelope Branch

## Current Objective

Wire BOOKING_AMENDED through the Python OTA adapter pipeline:

1. **semantics.py** — map `reservation_modified` → semantic kind `BOOKING_AMENDED`
   (currently maps to `MODIFY` which is rejected by default)

2. **service.py / pipeline.py** — allow `BOOKING_AMENDED` semantic kind to flow through
   to `to_canonical_envelope` and then `apply_envelope`
   (currently `MODIFY` is rejected before reaching apply_envelope)

3. **Contract tests** — `tests/test_booking_amended_contract.py`
   covering the full pipeline path for `reservation_modified` → BOOKING_AMENDED → APPLIED

## Key Invariants (Locked — Do Not Change)

- `apply_envelope` is the single write authority — no adapter reads/writes booking_state directly
- `event_log` is append-only
- `booking_id = "{source}_{reservation_ref}"` — deterministic, canonical

## Key Files for Phase 51

| File | Current behavior | Required change |
|------|-----------------|-----------------|
| `src/adapters/ota/semantics.py` | `reservation_modified` → MODIFY | → BOOKING_AMENDED |
| `src/adapters/ota/pipeline.py` | MODIFY → reject before envelope | Allow BOOKING_AMENDED through |
| `src/adapters/ota/service.py` | BOOKING_AMENDED not handled | Pass through like CREATED/CANCELED |
| `src/adapters/ota/bookingcom.py` | `to_canonical_envelope` raises on MODIFY | Handle BOOKING_AMENDED payload |

## Supabase

- Project: `reykggmlcehswrxjviup`
- URL: `https://reykggmlcehswrxjviup.supabase.co`
- Phase 50 migration deployed: `20260308210000_phase50_step2_apply_envelope_amended.sql`

## Tests

158 passing (2 pre-existing SQLite failures, unrelated)
