# Phase 91 — OTA Replay Harness

**Status:** Closed
**Prerequisite:** Phase 90 (External Integration Test Harness)
**Date Closed:** 2026-03-09

## Goal

Build a fixture-based replay harness that verifies the full pipeline is
deterministic across multiple runs when playing back recorded OTA payloads.

Where Phase 90 generates payloads at test-time, Phase 91 stores them as
static YAML fixtures and replays them, asserting that:
1. The same fixture always produces the same canonical envelope
2. The envelope type, provider, booking_id, and idempotency_key are stable
3. A mutated fixture produces a different (or rejected) envelope
4. All 8 providers have at least one CREATE and one CANCEL fixture

This is the foundation for a future regression suite — any adapter change
that alters the envelope produced by a recorded payload will be caught
immediately.

## Invariant (if applicable)

Pre-existing invariants preserved. No new invariants. No production code changes.
Fixtures are test infrastructure only.

## Design / Files

| File | Change |
|------|--------|
| `tests/fixtures/ota_replay/` | NEW directory — 16 YAML fixture files (1 CREATE + 1 CANCEL per provider) |
| `tests/test_ota_replay_harness.py` | EXISTS — replaced with Phase 91 fixture-driven implementation |

Wait — `test_ota_replay_harness.py` already exists (from earlier phase). Let me build the fixture infrastructure as:

| File | Change |
|------|--------|
| `tests/fixtures/ota_replay/*.yaml` | NEW — 16 YAML fixture files |
| `tests/test_ota_replay_fixture_contract.py` | NEW — fixture replay contract tests |

## Result

**1448 tests pass, 2 skipped.**
No Supabase schema changes. No new migrations. No production code changes.
