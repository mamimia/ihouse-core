# Phase 224 — Financial Explainer

**Status:** Closed
**Prerequisite:** Phase 223 (Manager Copilot v1)
**Date Closed:** 2026-03-11

## Goal

GET /ai/copilot/financial/explain/{booking_id} and GET /ai/copilot/financial/reconciliation-summary. 7 deterministic anomaly flags. Confidence tier (A/B/C) explanation. LLM overlay + heuristic fallback. Source: booking_financial_facts only.

## Design / Files

| File | Change |
|------|--------|
| `src/api/financial_explainer_router.py` | NEW — financial explainer + reconciliation summary |
| `src/main.py` | MODIFIED — financial_explainer_router registered |
| `tests/test_financial_explainer_contract.py` | NEW — 37 contract tests |

## Result

**37 tests pass.**
