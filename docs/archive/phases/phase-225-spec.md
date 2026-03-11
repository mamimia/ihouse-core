# Phase 225 — Task Recommendation Engine

**Status:** Closed
**Prerequisite:** Phase 224 (Financial Explainer)
**Date Closed:** 2026-03-11

## Goal

POST /ai/copilot/task-recommendations. Deterministic scoring: CRITICAL=1000, HIGH=500, MEDIUM=200, LOW=50 + SLA breach +800 + recency +50. LLM JSON-array rationale overlay (5 tasks, per-task).

## Design / Files

| File | Change |
|------|--------|
| `src/api/task_recommendation_router.py` | NEW — task scoring + recommendation endpoint |
| `src/main.py` | MODIFIED — task_recommendation_router registered |
| `tests/test_task_recommendation_contract.py` | NEW — 26 contract tests |

## Result

**26 tests pass.**
