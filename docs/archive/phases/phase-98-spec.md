# Phase 98 — Despegar Adapter (Tier 2 — Latin America)

**Status:** Closed
**Prerequisite:** Phase 97 (Klook Replay Fixture Contract)
**Date Closed:** 2026-03-09

## Goal

Integrate Despegar (despegar.com / decolar.com) as the 11th OTA adapter in iHouse Core. Despegar is the dominant OTA in Latin America, with leading market positions in Argentina, Brazil, Mexico, Chile, Colombia, and Peru. Adds multi-currency LATAM support (ARS, BRL, MXN, CLP, COP, PEN, USD).

Also fixed a latent gap in `payload_validator.py`: Rule 3 (booking identity) only accepted `reservation_id`, `booking_ref`, and `order_id`. Despegar uses `reservation_code`. Fixed by extending Rule 3 to accept `reservation_code` and `booking_code` as valid alternatives.

## Invariant

- `payload_validator.py` Rule 3 accepts: `reservation_id` | `booking_ref` | `order_id` | `reservation_code` | `booking_code`
- Despegar financial extractor: FULL when all 3 fields present; ESTIMATED when net derived; PARTIAL when fare or currency missing
- `booking_state` must NEVER contain financial calculations (reaffirmed)

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/despegar.py` | NEW — DespegarAdapter: reservation_code (DSP- strip), hotel_id→property_id, passenger_count, check_in/check_out, total_fare; events: BOOKING_CONFIRMED→CREATE, BOOKING_CANCELLED→CANCEL, BOOKING_MODIFIED→AMENDED |
| `src/adapters/ota/registry.py` | MODIFIED — DespegarAdapter registered under "despegar" |
| `src/adapters/ota/booking_identity.py` | MODIFIED — _strip_despegar_prefix: removes "DSP-" prefix (case-insensitive) |
| `src/adapters/ota/schema_normalizer.py` | MODIFIED — 6 helpers: _guest_count (passenger_count), _booking_ref (reservation_code), _property_id (hotel_id), _check_in (check_in), _check_out (check_out), _total_price (total_fare) |
| `src/adapters/ota/amendment_extractor.py` | MODIFIED — extract_amendment_despegar: modification.{check_in, check_out, passenger_count, reason}; added to _SUPPORTED_PROVIDERS |
| `src/adapters/ota/financial_extractor.py` | MODIFIED — _extract_despegar: total_fare/despegar_fee/net_amount; derived net = fare - fee when net absent (ESTIMATED); LATAM multi-currency note in docstring |
| `src/adapters/ota/payload_validator.py` | MODIFIED — Rule 3: reservation_code + booking_code accepted as booking identity alternatives |
| `tests/test_despegar_adapter_contract.py` | NEW — 61 tests, Groups A–H: registration, normalize (14 assertions), canonical envelope (CREATE/CANCEL/AMENDED), financial (FULL/ESTIMATED/PARTIAL + BRL), identity (DSP-), amendment (modification block), pipeline, idempotency |
| `docs/core/current-snapshot.md` | MODIFIED — Phase 98 entry, test count 1977→2038 |
| `docs/core/work-context.md` | MODIFIED — Phase 99 queued |

## Result

**2038 tests pass, 2 skipped.**
OTA adapters: 11 total (8 Tier 1 + MMT + Klook + Despegar).
No Supabase schema changes. No new migrations. No booking_state writes.
Git commit: 607e519
