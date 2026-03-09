# Phase 88 — Traveloka Adapter

**Status:** Closed
**Prerequisite:** Phase 87 — Tenant Isolation Hardening
**Date Closed:** 2026-03-09

## Market Context

Traveloka is the dominant OTA for Southeast Asia (Tier 1.5):
- #1 OTA in Indonesia, Thailand, Vietnam, Malaysia, Philippines
- Critical for operators with properties in Bali, Bangkok, and regional SE Asia
- Completes coverage alongside Agoda (Booking Holdings) and Trip.com

## Field Mapping

| Traveloka Field | Canonical Field |
|---|---|
| `booking_code` | `reservation_id` (TV- prefix stripped) |
| `property_code` | `property_id` |
| `check_in_date` | `canonical_check_in` |
| `check_out_date` | `canonical_check_out` |
| `num_guests` | `canonical_guest_count` |
| `booking_total` | `canonical_total_price` / `total_price` |
| `currency_code` | `canonical_currency` / `currency` (note: not `currency`) |
| `event_reference` | `external_event_id` |

## Event Type Mapping

| Traveloka Event | Semantic Kind | Canonical Type |
|---|---|---|
| `BOOKING_CONFIRMED` | CREATE | `BOOKING_CREATED` |
| `BOOKING_CANCELLED` | CANCEL | `BOOKING_CANCELED` |
| `BOOKING_MODIFIED` | BOOKING_AMENDED | `BOOKING_AMENDED` |

## Financial Logic

- `booking_total` → `total_price`
- `traveloka_fee` → `ota_commission` + `fees`
- `net_payout` → `net_to_property`
- If `net_payout` absent but `booking_total` + `traveloka_fee` present → derived: `net = booking_total - traveloka_fee` (confidence = ESTIMATED)
- `taxes` always None (Traveloka does not expose separately)
- Currency from `currency_code` field (not `currency`)

## Prefix Stripping

`_strip_traveloka_prefix`: strips `TV-` / `tv-` prefix from booking codes.
`booking_id = "traveloka_{stripped_code}"`

## Amendment Block

`modification.check_in_date`, `modification.check_out_date`, `modification.num_guests`, `modification.modification_reason`

## Files Changed

| File | Change |
|---|---|
| `src/adapters/ota/traveloka.py` | NEW — TravelokaAdapter |
| `src/adapters/ota/schema_normalizer.py` | Added traveloka to 7 field helpers + currency_code special case |
| `src/adapters/ota/financial_extractor.py` | Added `_extract_traveloka` + registered in `_EXTRACTORS` |
| `src/adapters/ota/amendment_extractor.py` | Added `extract_amendment_traveloka` + dispatcher + `_SUPPORTED_PROVIDERS` |
| `src/adapters/ota/booking_identity.py` | Added `_strip_traveloka_prefix` + registry entry |
| `src/adapters/ota/registry.py` | Imported + registered `TravelokaAdapter` |
| `tests/test_traveloka_adapter_contract.py` | NEW — 53 contract tests (Groups A-I) |

## Result

**1029 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
