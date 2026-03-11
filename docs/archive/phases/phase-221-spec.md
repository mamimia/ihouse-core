# Phase 221 — Scheduled Job Runner

**Status:** Closed
**Prerequisite:** Phase 220 (CI/CD Pipeline Foundation)
**Date Closed:** 2026-03-11

## Goal

Wire AsyncIOScheduler (APScheduler 3.x) into FastAPI lifespan. 3 scheduled jobs: SLA sweep (2min), DLQ threshold alert (10min), health log (15min). Add GET /admin/scheduler-status endpoint.

## Design / Files

| File | Change |
|------|--------|
| `src/services/scheduler.py` | NEW — APScheduler integration + 3 jobs |
| `src/main.py` | MODIFIED — scheduler lifespan + scheduler-status endpoint |
| `tests/test_scheduler_contract.py` | NEW — 32 contract tests |

## Result

**32 tests pass.**
