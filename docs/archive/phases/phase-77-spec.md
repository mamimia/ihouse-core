# Phase 77 — OTA Schema Normalization

**Status:** Closed
**Prerequisite:** Phase 76 (occurred_at vs recorded_at Separation)
**Date Closed:** 2026-03-09

## Goal

Unify inconsistent field names across all 5 OTA providers (Booking.com, Airbnb, Expedia, Agoda, Trip.com) into canonical field names at the adapter layer. Every provider uses different names for guest count, booking reference, and property ID — this phase introduces a single normalization layer that adds canonical keys without removing raw provider fields.

## Invariant

- `NormalizedBookingEvent.payload` always contains `canonical_guest_count`, `canonical_booking_ref`, and `canonical_property_id` after adapter normalization
- Raw provider fields are never removed — canonical keys are additive
- Missing provider fields → `None` (no `KeyError` raised)
- `normalize_schema()` returns a copy — original caller dict is never mutated

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/schema_normalizer.py` | NEW — `normalize_schema(provider, payload) -> dict` enriches payload with canonical keys |
| `src/adapters/ota/bookingcom.py` | MODIFIED — calls `normalize_schema()` in `normalize()` |
| `src/adapters/ota/airbnb.py` | MODIFIED — calls `normalize_schema()` in `normalize()` |
| `src/adapters/ota/expedia.py` | MODIFIED — calls `normalize_schema()` in `normalize()` |
| `src/adapters/ota/agoda.py` | MODIFIED — calls `normalize_schema()` in `normalize()` |
| `src/adapters/ota/tripcom.py` | MODIFIED — calls `normalize_schema()` in `normalize()` |
| `tests/test_schema_normalizer_contract.py` | NEW — 27 contract tests (Groups A–E) |
| `tests/test_agoda_contract.py` | MODIFIED — payload superset check (Phase 77 compat) |
| `tests/test_airbnb_contract.py` | MODIFIED — payload superset check (Phase 77 compat) |
| `tests/test_expedia_contract.py` | MODIFIED — payload superset check (Phase 77 compat) |
| `tests/test_tripcom_contract.py` | MODIFIED — payload superset check (Phase 77 compat) |

## Canonical Field Mapping

| Canonical Key | bookingcom | airbnb | expedia | agoda | tripcom |
|--------------|------------|--------|---------|-------|---------|
| `canonical_guest_count` | `number_of_guests` | `guest_count` | `guests.count` | `num_guests` | `guests` |
| `canonical_booking_ref` | `reservation_id` | `reservation_id` | `reservation_id` | `booking_ref` | `order_id` |
| `canonical_property_id` | `property_id` | `listing_id` | `property_id` | `property_id` | `hotel_id` |

## Result

**572 tests pass, 2 skipped.**
