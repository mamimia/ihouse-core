# Phase 125 — Hotelbeds Adapter (Tier 3 — EU/Global B2B Bedbank)

**Status:** Closed
**Prerequisite:** Phase 98 (Despegar Adapter)
**Date Closed:** 2026-03-09

## Goal

Add Hotelbeds as the 13th OTA provider. Hotelbeds is the world's largest B2B
bedbank — connects properties with wholesale travel buyers (agencies, TMCs,
tour operators). Explicit documentation of B2B vs. B2C payload semantics
per roadmap requirement.

## B2B vs. B2C Semantics (documented explicitly)

| Concept | B2C (Booking.com, Airbnb) | B2B (Hotelbeds) |
|---------|---------------------------|-----------------|
| Who pays property? | OTA remits net after deducting commission | Hotelbeds pays net_rate directly |
| gross amount | total_price (from guest) | contract_price (Hotelbeds charges buyer) |
| OTA's margin | ota_commission (deducted from gross) | markup_amount (added to net_rate) |
| net to property | total_price - commission | net_rate (direct) |
| primary booking unit | guest | room (room_count) |

## Files Changed

| File | Change |
|------|--------|
| `src/adapters/ota/hotelbeds.py` | NEW — HotelbedsAdapter (Tier 3) |
| `src/adapters/ota/financial_extractor.py` | MODIFIED — _extract_hotelbeds + _EXTRACTORS["hotelbeds"] |
| `src/adapters/ota/booking_identity.py` | MODIFIED — _strip_hotelbeds_prefix (HB-) + _PROVIDER_RULES["hotelbeds"] |
| `src/adapters/ota/amendment_extractor.py` | MODIFIED — extract_amendment_hotelbeds + dispatcher |
| `src/adapters/ota/registry.py` | MODIFIED — HotelbedsAdapter registered |
| `tests/test_hotelbeds_adapter_contract.py` | NEW — 42 tests |

## Hotelbeds Webhook Fields

| Field | Maps To |
|-------|---------|
| `voucher_ref` | reservation_id (HB- prefix stripped) |
| `hotel_code` | property_id |
| `event_id` | external_event_id |
| `contract_price` | total_price (gross — buyer pays Hotelbeds) |
| `net_rate` | net_to_property (property receives directly) |
| `markup_amount` | ota_commission (Hotelbeds' margin) |

## Amendment Block

Hotelbeds sends under `amendment`: `check_in`, `check_out`, `guest_count`, `room_count`, `reason`.
guest_count preferred; room_count used as fallback.

## Result

**3093 tests pass**, 2 pre-existing SQLite skips.
No DB schema changes. No booking_state changes.
