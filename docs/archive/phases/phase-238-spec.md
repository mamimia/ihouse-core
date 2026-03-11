# Phase 238 — Ctrip / Trip.com Enhanced Adapter

**Status:** Closed
**Prerequisite:** Phase 237 — Staging Environment & Integration Tests
**Date Closed:** 2026-03-11

## Goal

Upgrade the existing generic `tripcom.py` adapter for the Chinese market. Add Ctrip-specific field handling: CTRIP- prefix stripping, CNY-first currency default, Chinese guest name romanization fallback, and Ctrip cancellation reason codes. Add "ctrip" alias to the OTA registry.

## Invariant (Phase 238)

`tripcom.py` remains fully backward-compatible — existing Trip.com payloads with `order_id` and `TC-` prefix continue to work unchanged. New Ctrip fields are additive.

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/tripcom.py` | MODIFIED — full rewrite with Ctrip handling |
| `src/adapters/ota/booking_identity.py` | MODIFIED — `CTRIP-` prefix stripping added |
| `src/adapters/ota/registry.py` | MODIFIED — `"ctrip"` alias added |
| `tests/test_tripcom_enhanced_contract.py` | NEW — 15 contract tests |
| `docs/archive/phases/phase-238-spec.md` | NEW — this file |

## Key Design Choices

- `booking_ref` field takes priority over legacy `order_id`
- Chinese guest name → `"Guest (汉字)"` safe fallback (no pinyin library required)
- Currency defaults to CNY if not provided
- Cancellation codes: NC → no_charge, FC → full_charge, PC → partial_charge
- `provider` stays `"tripcom"` — `"ctrip"` is an alias in registry only

## Result

**15 contract tests pass.**
Backward-compatible. No breaking changes.
