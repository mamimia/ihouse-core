# Phase 251 — Dynamic Pricing Suggestion Engine

**Status:** Closed
**Prerequisite:** Phase 246 (Rate Cards)
**Date Closed:** 2026-03-11

## Goal

Turn static rate cards into dynamic 30-day rate suggestions using
occupancy, seasonality, and lead-time multipliers — no ML, fully deterministic.

## New Files

| File | Type | Description |
|------|------|-------------|
| `src/services/pricing_engine.py` | NEW | Pure function engine — suggest_prices() + PriceSuggestion + summary_stats |
| `src/api/pricing_suggestion_router.py` | NEW | GET /pricing/suggestion/{property_id} |
| `tests/test_pricing_suggestion_contract.py` | NEW | 37 contract tests (10 groups) |
| `src/main.py` | MODIFIED | Registered pricing_suggestion_router |

## Endpoint

`GET /pricing/suggestion/{property_id}?days=30&room_type=standard&occupancy_pct=75`

Returns: `property_id, room_type, currency, base_rate, summary{min,max,avg,count}, suggestions[{date, day, season, suggested_rate, ...}]`

## Algorithm

```
suggested = base_rate
          × seasonality   (high Nov-Mar: ×1.20 / low: ×0.90)
          × occupancy     (≥80%: ×1.25 / 60-79%: ×1.10 / 40-59%: ×1.00 / <40%: ×0.90)
          × lead_time     (0-2d: ×0.85 / 3-6d: ×0.90 / 7-13d: ×1.00 / ≥14d: ×1.05)
```

Rounded to nearest 100 THB. Max 90 days projection.

## Result

**~5,860 tests pass. 0 failures. Exit 0.** 37 new tests across 10 groups.
