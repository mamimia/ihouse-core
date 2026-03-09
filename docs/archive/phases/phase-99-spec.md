# Phase 99 — Despegar Replay Fixture Contract

**Status:** Closed
**Prerequisite:** Phase 98 (Despegar Adapter)
**Date Closed:** 2026-03-09

## Goal

Add Despegar replay fixtures to the OTA Replay Fixture Contract harness (Phase 91). Follows the same pattern as Phase 95 (MakeMyTrip replay) and Phase 97 (Klook replay). Extends `EXPECTED_PROVIDERS` from 10 to 11 and the fixture count invariant from 20 to 22 (11 providers × 2).

## Invariant

Replay fixture count invariant: **providers × 2**. With 11 providers: exactly **22 fixtures** required.
`test_e4_total_fixture_count_is_twenty_two` enforces this.

## Design / Files

| File | Change |
|------|--------|
| `tests/fixtures/ota_replay/despegar.yaml` | NEW — 2 YAML documents: `despegar_create` (BOOKING_CONFIRMED, ARS, DSP-AR-REPLAY-001, passenger_count=2, total_fare=75000.00, despegar_fee=11250.00, net_amount=63750.00) + `despegar_cancel` (BOOKING_CANCELLED, no net_amount) |
| `tests/test_ota_replay_fixture_contract.py` | MODIFIED — `EXPECTED_PROVIDERS` 10→11 (added `"despegar"`); `test_e4` renamed to `test_e4_total_fixture_count_is_twenty_two`, count 20→22; module docstring 10→11; D1 docstring: added `despegar → event_id (standard)` |

## Result

**2074 tests pass, 2 skipped.**
Replay harness: **375 tests** covering 11 providers × 2 fixtures each (+34 vs Phase 98).
No Supabase schema changes. No adapter code changes. No new migrations. No `booking_state` writes.
