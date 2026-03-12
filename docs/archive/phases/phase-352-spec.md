# Phase 352 — CI/CD Pipeline Hardening

**Closed:** 2026-03-12
**Category:** 🏗️ CI/CD / Core Infrastructure
**Test file:** `tests/test_pipeline_hardening_p352.py`

## Summary

Tests for foundational pipeline components: CoreExecutor validation
contract, InMemory testing ports (event log + applier + state store),
idempotency invariants (same key = same envelope_id, frozen dataclass),
and CI environment guard assertions.

## Tests Added: 24

### Group A — CoreExecutor Contract (6 tests)
- Unknown type, missing type, missing payload, missing occurred_at → CoreExecutionError
- No applier → ExecuteResult with warning; event appended to log

### Group B — InMemoryEventLogPort + Applier (6 tests)
- append_event returns idempotency_key, all_envelopes ordered, empty key raises
- Applier always returns APPLIED, stores results, projection set/fetch

### Group C — InMemoryStateStorePort (4 tests)
- Fresh store has no keys, commit_upserts stores state by key,
  multiple upserts accumulate separate keys, ensure_schema is no-op

### Group D — Idempotency (4 tests)
- Same key → same envelope_id, different keys → different ids,
  two execute() calls → two events, ExecuteResult is frozen

### Group E — CI Guard (4 tests)
- IHOUSE_ENV=test, SUPABASE_URL set, DEV_MODE recognizable, executor importable

## System Numbers

| Metric | Before | After |
|--------|--------|-------|
| Tests collected | 7,023 | 7,047 |
| Test files | 235 | 236 |
| New tests | — | 24 |
