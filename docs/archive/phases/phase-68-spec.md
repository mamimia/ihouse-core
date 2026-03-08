# Phase 68 — booking_id Stability

**Status:** Closed
**Prerequisite:** Phase 67 (Financial Facts Query API)
**Date Closed:** 2026-03-09

## Goal

Protect booking_id stability across provider schema variations. All 5 OTA adapters previously passed `reservation_ref` raw from the provider payload into the canonical identity formula `{source}_{reservation_ref}`. If a provider changes capitalization, adds whitespace, or prepends a prefix (e.g. `BK-`, `AGD-`, `TC-`), the same booking would produce a different `booking_id`, bypassing dedup and creating ghost bookings.

This phase introduces `booking_identity.py` — a pure, deterministic normalization module — and wires it into all 5 adapter `normalize()` methods. The locked formula `booking_id = {source}_{reservation_ref}` (Phase 36) is unchanged. The `reservation_ref` is now normalized before use.

Also updates `future-improvements.md` to mark DLQ-related items as resolved (they were completed in Phases 39–41 but remained listed as open).

## Invariant (if applicable)

- `booking_id = {source}_{reservation_ref}` formula is unchanged (Phase 36, still locked)
- `normalize_reservation_ref()` is deterministic and pure — same input always produces same output
- No booking_state reads, no DB I/O, no side effects in the normalization layer

## Design / Files

| File | Change |
|------|--------|
| `src/adapters/ota/booking_identity.py` | NEW — `normalize_reservation_ref(provider, raw_ref)` + `build_booking_id(source, ref)`; per-provider rules (strip, lowercase, prefix stripping) |
| `tests/test_booking_identity_contract.py` | NEW — 30 contract tests: base normalization, all 5 providers, unknown provider fallback, determinism, `build_booking_id` |
| `src/adapters/ota/bookingcom.py` | MODIFIED — `normalize()` calls `normalize_reservation_ref(self.provider, payload["reservation_id"])` |
| `src/adapters/ota/expedia.py` | MODIFIED — same |
| `src/adapters/ota/airbnb.py` | MODIFIED — same (Airbnb uses `listing_id` for property, unchanged) |
| `src/adapters/ota/agoda.py` | MODIFIED — `payload["booking_ref"]` now normalized |
| `src/adapters/ota/tripcom.py` | MODIFIED — `payload["order_id"]` now normalized |
| `docs/core/improvements/future-improvements.md` | MODIFIED — DLQ items marked resolved |

## Result

**431 tests pass, 2 skipped.**
Pre-existing 2 SQLite skips unchanged. 30 new booking_identity contract tests added (previously 396 passed + 5 adapter test suites unchanged).
No Supabase schema changes. No new tables or migrations.
