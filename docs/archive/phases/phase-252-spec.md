# Phase 252 — Owner Financial Report API v2

**Status:** Closed
**Prerequisite:** Phase 116+ (booking_financial_facts)
**Date Closed:** 2026-03-11

## Goal

Self-serve owner financial report with custom date ranges and drill-down
by property, OTA, or individual booking. Reads booking_financial_facts.

## Endpoint

`GET /owner/financial-report?date_from=2026-01-01&date_to=2026-03-31&drill_down=property`

### Query params
| Param | Required | Description |
|-------|----------|-------------|
| date_from | yes | ISO date start |
| date_to | yes | ISO date end |
| property_id | no | filter to one property |
| ota | no | filter to one OTA |
| drill_down | no | "property" (default), "ota", "booking" |
| page / page_size | no | pagination (max 200) |

### Response
summary + breakdown[] + pagination + exported_csv_url (null placeholder)

## Files

| File | Change |
|------|--------|
| `src/api/owner_financial_report_v2_router.py` | NEW |
| `src/main.py` | MODIFIED |
| `tests/test_owner_financial_report_v2_contract.py` | NEW — 31 tests (9 groups) |

## Result

**Full suite Exit 0. 0 regressions.**
