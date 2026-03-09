# Phase 85 — Google Vacation Rentals (GVR) Adapter

**Status:** Closed
**Prerequisite:** Phase 84 — Reservation Timeline
**Date Closed:** 2026-03-09

## Goal

Add GVR as the 7th OTA adapter. GVR is a **distribution surface** (not a classic OTA marketplace), so its adapter architecture is documented explicitly.

## GVR vs Classic OTAs — Key Difference

| Aspect | Classic OTA | Google Vacation Rentals |
|---|---|---|
| Role | Marketplace / booking engine | Distribution surface (Google Search/Maps/Hotels) |
| Guest relationship | OTA owns | Property manager or connected OTA owns |
| Payment | OTA processes | No GVR direct payment in standard mode |
| Booking delivery | OTA webhook | GVR notification, or via connected OTA channel |
| `reservation_id` field | `reservation_id` | `gvr_booking_id` |
| Extra canonical field | — | `connected_ota` (forwarded OTA channel) |

**Adapter pattern is IDENTICAL** — normalize → classify → to_canonical_envelope.

## GVR Field Mapping

| Canonical Field | GVR Field |
|---|---|
| `property_id` | `property_id` (standard) |
| `canonical_check_in` | `check_in` |
| `canonical_check_out` | `check_out` |
| `canonical_guest_count` | `guest_count` |
| `canonical_total_price` | `booking_value` |
| `net_to_property` | `net_amount` (derived if absent: `booking_value - google_fee`) |
| `ota_commission` / `fees` | `google_fee` |
| `taxes` | None (GVR does not expose taxes) |
| Extra | `connected_ota` forwarded in CREATE/CANCEL envelopes |

## Financial Logic

- `source_confidence = FULL` if `booking_value + currency` present
- `source_confidence = ESTIMATED` if `net_amount` is derived from `booking_value - google_fee`
- `source_confidence = PARTIAL` if `booking_value` or `currency` missing

## Amendment Pattern

GVR uses `modification.*` key (same semantic as agoda's `modification.*`):
```json
{"modification": {"check_in": "...", "check_out": "...", "guest_count": 2, "reason": "..."}}
```

## Files

| File | Change |
|---|---|
| `src/adapters/ota/gvr.py` | NEW — GVRAdapter with full architectural notes |
| `tests/test_gvr_adapter_contract.py` | NEW — 50 contract tests (Groups A–I) |
| `src/adapters/ota/schema_normalizer.py` | gvr added to all 7 canonical field helpers |
| `src/adapters/ota/financial_extractor.py` | `_extract_gvr` added |
| `src/adapters/ota/amendment_extractor.py` | `extract_amendment_gvr` added |
| `src/adapters/ota/booking_identity.py` | gvr added to `_PROVIDER_RULES` |
| `src/adapters/ota/registry.py` | GVRAdapter registered |

## Result

**862 passed, 2 skipped.**
No Supabase schema changes. No new migrations.
