# Phases 626–645 — Wave 3: Task System Enhancement

## Overview

Wave 3 builds the **Cleaning & Maintenance System** on top of the existing task infrastructure from Waves 1–2. All database tables (`cleaning_checklist_templates`, `cleaning_task_progress`, `cleaning_photos`) were created in Phase 600 (Wave 1 migration) — no new migrations required.

## New Files

| File | Purpose | Phase |
|------|---------|-------|
| `src/api/cleaning_task_router.py` | 8 endpoints: template CRUD, progress, photos, supplies, complete, comparison | 626–632 |
| `src/tasks/cleaning_template_seeder.py` | Default EN+TH checklist (21 items, 7 supply checks) | 627 |
| `src/api/worker_calendar_router.py` | 2 endpoints: calendar view, today's tasks | 635 |
| `tests/test_wave3_task_enhancement_contract.py` | 39 contract + E2E tests | 636–645 |

## Modified Files

| File | Change | Phase |
|------|--------|-------|
| `src/tasks/task_automator.py` | +`check_out` param, emits CHECKOUT_VERIFY, reschedule on amended | 634 |
| `src/tasks/task_router.py` | +`GET /tasks/{id}/navigate` (GPS + Google Maps) | 633 |
| `src/main.py` | +2 router registrations (Wave 3 section) | 626, 635 |

## API Endpoints Added (11 total)

| Method | Path | Phase |
|--------|------|-------|
| POST | `/properties/{id}/cleaning-checklist` | 626 |
| GET | `/properties/{id}/cleaning-checklist` | 626 |
| POST | `/tasks/{id}/start-cleaning` | 628 |
| PATCH | `/tasks/{id}/cleaning-progress` | 628 |
| POST | `/tasks/{id}/cleaning-photos` | 629 |
| PATCH | `/tasks/{id}/supply-check` | 630 |
| POST | `/tasks/{id}/complete-cleaning` | 631 |
| GET | `/tasks/{id}/reference-vs-cleaning` | 632 |
| GET | `/tasks/{id}/navigate` | 633 |
| GET | `/workers/{id}/calendar` | 635 |
| GET | `/workers/{id}/tasks/today` | 635 |

## Key Design Decisions

1. **Template fallback chain**: property-specific → tenant global → hardcoded default
2. **Completion blocking**: 3 pre-conditions (items ✓, photos ✓, supplies ✓) + `force_complete` override
3. **CHECKOUT_VERIFY**: backward-compatible — only emitted when `check_out` is provided
4. **Worker calendar**: filters terminal tasks (COMPLETED, CANCELED) before grouping

## Test Coverage

- 39 tests in `test_wave3_task_enhancement_contract.py`
- Full regression: 7,495 passed, 0 failed, 22 skipped
- Zero regressions introduced
