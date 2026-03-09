# Phase 78 — OTA Schema Normalization (Dates + Price)

**Status:** Closed
**Prerequisite:** Phase 77 — OTA Schema Normalization
**Date Closed:** 2026-03-09

## Goal

Extend `schema_normalizer.py` (Phase 77) with 4 additional canonical keys covering date and price fields. Provider-specific field names for check-in/check-out dates and price totals are inconsistent across all 5 OTA providers. This phase adds a uniform extraction layer that returns raw strings, preserving all original provider fields.

## Invariant

- `schema_normalizer.py` returns only raw `str` values for date/price keys — no type conversion
- `financial_extractor.py` owns Decimal precision; `schema_normalizer.py` never converts to Decimal
- All canonical keys remain additive — raw provider fields are never removed

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/schema_normalizer.py` | MODIFIED — 4 new helpers + 4 new canonical keys added |
| `tests/test_schema_normalizer_contract.py` | MODIFIED — Groups F–I appended (26 new tests) |

### Provider field mapping

| Canonical Key | bookingcom | airbnb | expedia | agoda | tripcom |
|---|---|---|---|---|---|
| `canonical_check_in` | `check_in` | `check_in` | `check_in_date` | `check_in` | `arrival_date` |
| `canonical_check_out` | `check_out` | `check_out` | `check_out_date` | `check_out` | `departure_date` |
| `canonical_currency` | `currency` | `currency` | `currency` | `currency` | `currency` |
| `canonical_total_price` | `total_price` | `booking_subtotal` | `total_amount` | `selling_rate` | `order_amount` |

## Result

**598 passed, 2 skipped.**
No Supabase schema changes. No new migrations. No adapter changes required.
