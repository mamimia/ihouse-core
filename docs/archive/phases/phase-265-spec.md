# Phase 265 — Test Suite Repair + Documentation Integrity Sync

**Status:** Closed
**Prerequisite:** Phase 264 (Advanced Analytics + Platform Checkpoint XI)
**Date Closed:** 2026-03-11

## Goal

Repair the test suite (5 files failing to collect), enforce the Domaniqo/iHouse Core
branding boundary as a hard system invariant, and sync stale canonical documents to
reflect the state after Phases 255–264.

## Invariants

- `inside = iHouse Core` — all internal system names stay as-is
- `outside = Domaniqo` — only user-facing surfaces use Domaniqo branding
- Updating `brand-handoff.md` never triggers internal renames (documented in BOOT.md, governance.md, brand-handoff.md)

## Design / Files

| File | Change |
|------|--------|
| `pytest.ini` | MODIFIED — added `pythonpath = src` (root cause of 5 broken test collections) |
| `src/main.py` | MODIFIED — branding temporarily changed to Domaniqo Core, then reverted to iHouse Core per invariant |
| `tests/test_main_app.py` | MODIFIED — `test_app_title` reverted to expect `"iHouse Core"` |
| `docs/core/live-system.md` | MODIFIED — header updated to Phase 265; +5 API endpoint groups (P259-264) |
| `docs/core/roadmap.md` | MODIFIED — system numbers updated (72→77 routers, ~5,900→~6,024 tests, Phase 254→265) |
| `docs/core/current-snapshot.md` | MODIFIED — Last Closed Phase → 265 |
| `docs/core/phase-timeline.md` | APPENDED — Phase 265 entry |
| `docs/core/brand-handoff.md` | MODIFIED — added "⚠️ Hard Branding Boundary" section (inside/outside table) |
| `docs/core/governance.md` | MODIFIED — added "Branding Boundary — Irrevocable" section |
| `docs/core/BOOT.md` | MODIFIED — added "Branding boundary — hard rule" section after Safety rails |

## Result

**6,024 tests pass, 13 skipped, 0 failures.**
Branding boundary codified in BOOT.md, governance.md, and brand-handoff.md.
