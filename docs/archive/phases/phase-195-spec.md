# Phase 195 — Hostelworld Adapter (Tier 3 — Hostel/Budget Market)

**Closed:** 2026-03-10  
**Type:** OTA Adapter  
**Risk:** Low  

## Goal

Extend iHouse Core OTA coverage to the global hostel/budget market by implementing the Hostelworld adapter — the dominant global hostel OTA (70%+ of online hostel bookings, 13M+ customers, 17,000+ properties worldwide). Critical for budget-segment operators in Bangkok, Chiang Mai, and European markets.

## Changes

### `src/adapters/ota/hostelworld.py` [NEW]
`HostelworldAdapter` following the standard adapter interface (Phase 35+):
- `provider = "hostelworld"`
- `normalize()` — maps `reservation_id → reservation_id` (HW- prefix stripped), `property_id → property_id` (direct, no alias), delegates to `schema_normalizer`, `financial_extractor`
- `to_canonical_envelope()` — produces `BOOKING_CREATED`, `BOOKING_CANCELED`, `BOOKING_AMENDED` envelopes

### `src/adapters/ota/booking_identity.py` [MODIFY]
- Added `_strip_hostelworld_prefix()` — strips `HW-` prefix from reservation IDs
- Added `"hostelworld": [_strip_hostelworld_prefix]` to `_PROVIDER_RULES`

### `src/adapters/ota/registry.py` [MODIFY]
- Import: `from .hostelworld import HostelworldAdapter`
- `"hostelworld": HostelworldAdapter()` added to `_ADAPTERS`

### `src/adapters/ota/financial_extractor.py` [MODIFY]
- Added `_extract_hostelworld()` handling `total_price`, `hostelworld_fee`, `net_price`, `currency`
- Net derivation: `net = total_price - hostelworld_fee` if `net_price` absent → `ESTIMATED` confidence
- Registered: `_EXTRACTORS["hostelworld"] = _extract_hostelworld`

### `src/adapters/ota/schema_normalizer.py` [MODIFY]
- `_guest_count`: `elif provider == "hostelworld" → int(payload["guest_count"])`  
- `_booking_ref`: `elif provider == "hostelworld" → str(payload["reservation_id"])`  
- `_property_id`: `elif provider == "hostelworld" → str(payload["property_id"])` (direct)

### `src/adapters/ota/amendment_extractor.py` [MODIFY]
- Added `extract_amendment_hostelworld()` — reads from `amendment` block (distinct from Rakuten's `modification` block)
- Added `"hostelworld"` to `_SUPPORTED_PROVIDERS`
- Added `elif normalized_provider == "hostelworld"` branch in dispatcher

## Webhook Schema

| Field | Maps To | Notes |
|-------|---------|-------|
| `reservation_id` | `reservation_id` | HW- prefix stripped |
| `property_id` | `property_id` | Direct — no alias |
| `event_id` | `external_event_id` | Idempotency |
| `total_price` | `canonical_total_price` | Gross |
| `hostelworld_fee` | `ota_commission` + `fees` | Optional |
| `net_price` | `net_to_property` | Optional, derived if absent |
| `currency` | `canonical_currency` | EUR/GBP/USD/THB primary |
| `amendment.*` | amendment block | BOOKING_MODIFIED only |

## Prefix Stripping

`"HW-2025-0081234"` → `"2025-0081234"` (lowercase, prefix removed)

## Tests

**`tests/test_hostelworld_adapter_contract.py`** — 37 tests, Groups A–G:
- A (6): `normalize()` field mapping
- B (5): HW- prefix stripping
- C (3): Event type → semantic kind
- D (4): Financial extraction with dataclass attribute access
- E (4): Amendment extraction via `amendment` block
- F (8): `to_canonical_envelope()` shape and idempotency
- G (7): Replay fixture round-trip (CREATE + CANCEL)

**`tests/fixtures/ota_replay/hostelworld.yaml`** — CREATE + CANCEL fixture events

## Verification

```
37 passed in 0.11s   (hostelworld suite)
exit code 0          (full suite — pre-existing webhook failures unchanged)
```

## OTA Coverage After Phase 195

12 providers: bookingcom, airbnb, expedia, agoda, tripcom, vrbo, gvr, traveloka, makemytrip, klook, despegar, rakuten, **hostelworld**
