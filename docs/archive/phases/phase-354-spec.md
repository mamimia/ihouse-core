# Phase 354 — Platform Checkpoint XVII

**Status:** Closed
**Prerequisite:** Phase 353 (Doc Auto-Generation from Code)
**Date Closed:** 2026-03-12

## Goal

Full platform audit — run entire test suite, verify documentation accuracy
against actual codebase metrics, correct all misaligned data in Layer C
canonical docs, and produce a handoff for the next session.

## Invariant

current-snapshot.md must reflect actual test results (including failures)
and list all closed phases up to the current one.

## Design / Files

| File | Change |
|------|--------|
| `docs/core/current-snapshot.md` | MODIFIED — appended phases 337-354, corrected test count to actual (7,022 passed, 30 failed, 17 skipped) |
| `docs/core/work-context.md` | MODIFIED — set current phase to 355 |
| `docs/core/phase-timeline.md` | MODIFIED — appended Phase 354 closure |
| `docs/core/construction-log.md` | MODIFIED — appended Phase 354 entry |
| `docs/archive/phases/phase-354-spec.md` | NEW |
| `releases/phase-zips/iHouse-Core-Docs-Phase-354.zip` | NEW |
| `releases/handoffs/handoff_to_new_chat Phase-354.md` | NEW |

## Result

**7,069 tests collected (7,022 passed, 30 failed [pre-existing cancel/amend adapter tests], 17 skipped).**
30 failures are pre-existing in `test_sync_cancel_contract.py` (10) and
`test_sync_amend_contract.py` (20) — cancel/amend HTTP mock tests use
stale mock patterns. Not introduced in this session.
