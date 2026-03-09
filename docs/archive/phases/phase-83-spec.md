# Phase 83 — Vrbo Adapter

**Status:** Closed
**Prerequisite:** Phase 82 — Admin Query API
**Date Closed:** 2026-03-09

## Goal

Add Vrbo (Vacation Rentals by Owner) as the 6th OTA provider adapter, following the same pattern as bookingcom/airbnb/expedia/agoda/tripcom.

## Files Created

| File | Description |
|---|---|
| `src/adapters/ota/vrbo.py` | VrboAdapter — normalize(), to_canonical_envelope() |
| `tests/test_vrbo_adapter_contract.py` | 43 contract tests (Groups A–H) |

## Files Modified

| File | Change |
|---|---|
| `src/adapters/ota/schema_normalizer.py` | Added vrbo to all 7 canonical field helpers. Supports 6 providers. |
| `src/adapters/ota/financial_extractor.py` | Added `_extract_vrbo` — traveler_payment/manager_payment/service_fee |
| `src/adapters/ota/amendment_extractor.py` | Added `extract_amendment_vrbo` — uses `alteration.*` pattern |
| `src/adapters/ota/booking_identity.py` | Added vrbo to `_PROVIDER_RULES` (no prefix stripping needed) |
| `src/adapters/ota/registry.py` | Registered `VrboAdapter` as provider `"vrbo"` |

## Vrbo Field Mapping

| Canonical Field | Vrbo Field |
|---|---|
| `property_id` | `unit_id` |
| `canonical_check_in` | `arrival_date` |
| `canonical_check_out` | `departure_date` |
| `canonical_guest_count` | `guest_count` |
| `canonical_total_price` | `traveler_payment` |
| `net_to_property` | `manager_payment` |
| `fees` / `ota_commission` | `service_fee` |

## Result

**767 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
