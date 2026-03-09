# Phase 78 — OTA Schema Normalization (Dates + Price)

## Status: CLOSED

## Objective

Extend `schema_normalizer.py` (Phase 77) with 4 additional canonical keys covering date and price fields across all 5 OTA providers.

## Problem

Provider date and price field names are inconsistent:

| Canonical Key | bookingcom | airbnb | expedia | agoda | tripcom |
|---|---|---|---|---|---|
| `canonical_check_in` | `check_in` | `check_in` | `check_in_date` | `check_in` | `arrival_date` |
| `canonical_check_out` | `check_out` | `check_out` | `check_out_date` | `check_out` | `departure_date` |
| `canonical_currency` | `currency` | `currency` | `currency` | `currency` | `currency` |
| `canonical_total_price` | `total_price` | `booking_subtotal` | `total_amount` | `selling_rate` | `order_amount` |

## Design

- Same rules as Phase 77: additive-only, raw fields preserved, missing → None
- `canonical_total_price` returns raw `str` — no Decimal conversion (financial_extractor owns precision)
- `canonical_check_in` / `canonical_check_out` return raw `str` — callers decide format
- No adapter changes required — all adapters already call `normalize_schema()`

## Files Changed

- `src/adapters/ota/schema_normalizer.py` — 4 new helpers + 4 new keys in `normalize_schema()`
- `tests/test_schema_normalizer_contract.py` — Groups F–I appended (26 new tests)

## Invariants (Unchanged)

- `apply_envelope` is the only write authority
- `booking_state` never contains financial data
- All canonical keys are additive — raw fields are never removed

## Result

**598 passed, 2 skipped** (pre-existing SQLite skips, unrelated)  
53 tests in test_schema_normalizer_contract.py (27 Phase 77 + 26 Phase 78)  
No Supabase schema changes. No migrations.
