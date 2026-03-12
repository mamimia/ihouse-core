# Phase 301 — Owner Portal Rich Data Service

**Status:** Closed  
**Prerequisite:** Phase 298 (Owner Portal Access), Phase 300 (Checkpoint XIV)  
**Date Closed:** 2026-03-12

## Goal

Enrich the Owner Portal with real data from `booking_state` and `booking_financial_facts`. Transform the Phase 298 stub summary (that returned a flat booking count and revenue total) into a rich property dashboard view.

## Design Decisions

- All queries are **property-scoped** — never cross-property data leaks
- Financial data gated on `role == 'owner'` — viewers see booking data only
- Two-step financial query: get `booking_ids` from `booking_state`, then join to `booking_financial_facts`
- **Best-effort** — all DB exceptions produce partial data, never raise to caller
- Occupancy: rolling 30-day window, clamped to period boundary
- 90-day rolling window for financial totals

## Files Changed

| File | Change |
|------|--------|
| `src/services/owner_portal_data.py` | NEW — 6 functions |
| `src/api/owner_portal_router.py` | MODIFIED — summary endpoint upgrade |
| `tests/test_owner_portal_data.py` | NEW — 18 tests (all pass) |

## API Surface Change

`GET /owner/portal/{property_id}/summary` — Phase 298 returned:
```json
{"property_id": "...", "role": "owner", "recent_bookings_count": 3}
```

Phase 301 returns:
```json
{
  "property_id": "...",
  "role": "owner",
  "booking_counts": {"total": 10, "confirmed": 7, "cancelled": 2, "checked_in": 1, ...},
  "upcoming_bookings": [{"booking_ref": "...", "check_in_date": "...", "nights": 3, ...}],
  "occupancy": {"occupancy_pct": 46.7, "occupied_nights": 14, "period_days": 30},
  "financials": {
    "period_days": 90,
    "gross_revenue_total": 5000.0,
    "net_revenue_total": 4200.0,
    "management_fee_total": 500.0,
    "ota_commission_total": 300.0,
    "booking_count_with_financials": 8
  }
}
```

`financials` key is absent for `role='viewer'`.

## Result

**18 new tests pass (18/18). All existing tests unaffected.**
