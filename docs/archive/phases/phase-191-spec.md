# Phase 191 — Multi-Currency Financial Overview

**Opened:** 2026-03-10  
**Closed:** 2026-03-10  
**Status:** ✅ Closed

## Goal

Expose a flat, portfolio-level view of financial performance across all currencies for a given month, sorted by gross revenue descending. Prerequisites Phase 116/161 aggregation layer reused unchanged; this phase adds only a new read endpoint and UI section.

## New / modified files

| File | Change |
|------|--------|
| `src/api/financial_aggregation_router.py` | + `GET /financial/multi-currency-overview` |
| `tests/test_multi_currency_overview_contract.py` | NEW — 15 tests |
| `ihouse-ui/lib/api.ts` | + `CurrencyOverviewRow`, `MultiCurrencyOverviewResponse`, `api.getMultiCurrencyOverview()` |
| `ihouse-ui/app/financial/page.tsx` | + `PortfolioOverview` component + Section 0 |

## Endpoint

```
GET /financial/multi-currency-overview?period=YYYY-MM[&currency=THB]
```

Response:
```json
{
  "tenant_id": "t1",
  "period": "2026-03",
  "total_bookings": 42,
  "currencies": [
    { "currency": "THB", "booking_count": 28, "gross_total": "450000.00",
      "net_total": "382500.00", "avg_commission_rate": "15.00" },
    { "currency": "USD", "booking_count": 14, "gross_total": "18200.00",
      "net_total": "15470.00", "avg_commission_rate": "15.00" }
  ]
}
```

## Invariants preserved

- No cross-currency arithmetic
- Reads `booking_financial_facts` only
- Owner property scoping (Phase 166) respected
- `avg_commission_rate` = `null` when gross = 0 (no ÷0)

## UI — Portfolio Overview section

- First section on `/financial` page (above existing Portfolio Summary)
- CSS mini horizontal bar chart per currency — width proportional to gross vs max
- Colour-coded currency badge (THB=amber, USD=blue, EUR=indigo, etc.)
- Hover row highlight
- Avg commission rate pill (amber) or — if null

## Tests

```
PYTHONPATH=src pytest tests/test_multi_currency_overview_contract.py -v
→ 15 passed
Full suite → exit 0, 0 regressions
```
