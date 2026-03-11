# Phase 271 — E2E DLQ & Replay Integration Test

**Status:** Closed
**Prerequisite:** Phase 270 (E2E Admin & Properties)
**Date Closed:** 2026-03-11

## Goal

Add direct async function call E2E tests for the DLQ (Dead Letter Queue) admin surface:
list, get single, and replay. CI-safe — no live DB, no staging, no real replay needed.

## Design

All 3 handlers (`list_dlq_entries`, `get_dlq_entry`, `replay_dlq_entry`) support `client=` injection.
`replay_dlq_entry` additionally supports `_replay_fn=` injection — allows deterministic replay
simulation without touching Supabase or the real `replay_dlq_row` function.

## Files

| File | Change |
|------|--------|
| `tests/test_dlq_e2e.py` | NEW — 22 tests, 3 groups (A-C) |

## Test Groups

| Group | Tests | Description |
|-------|-------|-------------|
| A | 7 | `list_dlq_entries`: shape, total, empty 0, invalid status 400, invalid limit 400, status/source filter propagation |
| B | 4 | `get_dlq_entry`: 200 + envelope_id, source field, 404 ghost |
| C | 7 | `replay_dlq_entry`: SUCCESS result, envelope_id in response, trace_id present, 404 ghost, already_replayed=True guard, FAILED result |

## Key Design Patterns

- `_replay_fn_success(row_id)` and `_replay_fn_fail(row_id)` are injectable mock functions
- `already_replayed` guard: when `replay_result == "APPLIED"`, returns 200 with `already_replayed: True` without calling replay

## Result

**22/22 passed on first run (clean 100%). ~6,183 total tests, 0 failures.**
