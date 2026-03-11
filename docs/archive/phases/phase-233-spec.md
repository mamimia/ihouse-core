# Phase 233 — Revenue Forecast Engine

## Goal

Forward-looking revenue projection using confirmed bookings in `booking_state`
and historical averages from `booking_financial_facts`.

## Invariants

- **Read-only:** zero DB writes (ai_audit_log is best-effort)
- **No cross-currency arithmetic:** each currency is independent
- **Graceful degradation:** missing financial data falls back to 90-day historical avg
- **Heuristic-first:** LLM overlay only when `OPENAI_API_KEY` set

## Endpoint

`GET /ai/copilot/revenue-forecast?window=30|60|90&property_id=<id>&currency=<iso>`

## Files

### New
- `src/api/revenue_forecast_router.py` — forecast endpoint + projection helpers
- `tests/test_revenue_forecast_contract.py` — 22 contract tests
- `docs/archive/phases/phase-233-spec.md` — this file

### Modified
- `src/main.py` — `revenue_forecast_router` registered (Phase 233)

## Response Shape

```json
{
  "tenant_id": "...",
  "generated_at": "...",
  "window_days": 30,
  "property_id": null,
  "currency_filter": null,
  "forecast": {
    "confirmed_bookings": 12,
    "projected_gross": "84000.00",
    "projected_net": "71400.00",
    "currency": "THB",
    "occupancy_pct": 40.0,
    "total_nights_analyzed": 30,
    "booked_nights": 12
  },
  "historical_avg": {
    "avg_gross_per_booking": "7000.00",
    "avg_net_per_booking": "5950.00",
    "sample_bookings": 48,
    "lookback_days": 90
  },
  "narrative": "...",
  "properties_included": ["prop-1"]
}
```

## Occupancy Calculation

`occupancy_pct = (booked_nights / (window_days × property_count)) × 100`

For single-property requests: `property_count = 1`.
For portfolio: `property_count = distinct properties with confirmed bookings in window`.
