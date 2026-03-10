# Phase 187 — Rakuten Travel Adapter — Japan Market

**Status:** Closed
**Prerequisite:** Phase 186 (Auth & Logout Flow)
**Date Closed:** 2026-03-10

## Goal

Add Rakuten Travel (楽天トラベル) as a Tier 3 OTA adapter. Rakuten is Japan's dominant domestic OTA (~40% market share by room-nights), and is essential for operators targeting the domestic Japanese traveler segment. This phase follows the established adapter pattern and adds all hook points: prefix stripping, schema normalization, financial extraction, amendment extraction, semantics, and registry.

## Invariant

booking_id format for Rakuten: `rakuten_{normalized_ref}` where normalized_ref has the RAK- prefix stripped (case-insensitive).

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/rakuten.py` | NEW — RakutenAdapter: hotel_code→property_id, RAK- prefix, JPY primary, BOOKING_CREATED/CANCELLED/MODIFIED |
| `src/adapters/ota/registry.py` | MODIFIED — "rakuten": RakutenAdapter() |
| `src/adapters/ota/booking_identity.py` | MODIFIED — _strip_rakuten_prefix() + _PROVIDER_RULES["rakuten"] |
| `src/adapters/ota/schema_normalizer.py` | MODIFIED — 5 field helpers (guest_count, booking_ref, hotel_code, check_in/out, total_amount) |
| `src/adapters/ota/financial_extractor.py` | MODIFIED — _extract_rakuten(): total_amount, rakuten_commission, net derivation, FULL/ESTIMATED/PARTIAL |
| `src/adapters/ota/amendment_extractor.py` | MODIFIED — extract_amendment_rakuten(): modification.{check_in,check_out,guest_count,reason} |
| `src/adapters/ota/semantics.py` | MODIFIED — "booking_created" → CREATE alias added |
| `tests/test_rakuten_adapter_contract.py` | NEW — 34 contract tests (Groups A-G) |

## Result

**4,420 tests pass. 0 regressions.**
Rakuten adapter fully wired. All 7 hook points registered. Financial extractor supports JPY and net derivation. Semantics alias covers Rakuten native event type strings.
