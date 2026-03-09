# Phase 104 — Amendment History Query API

**Status:** Closed
**Date Closed:** 2026-03-09

## Goal

Expose amendment financial history via HTTP. New `GET /amendments/{booking_id}` endpoint. Reads `booking_financial_facts` filtered by `event_kind = 'BOOKING_AMENDED'` (ORDER BY `recorded_at ASC`). Returns a chronological list of financial snapshots from each amendment event. Distinguishes between:
- Unknown booking → **404** (no rows at all for this tenant+booking_id)
- Known booking, never amended → **200 + empty list** (not a 404)
- Known booking with amendments → **200 + list**

## Invariant

- Never reads `booking_state`. Tenant isolation at DB level (`.eq("tenant_id", tenant_id)`).
- Amendment rows live in `booking_financial_facts` (same table as BOOKING_CREATED) — `event_kind` is the discriminator field.
- No writes of any kind.

## Design / Files

| File | Change |
|------|--------|
| `src/api/amendments_router.py` | NEW — `GET /amendments/{booking_id}`; JWT auth; `BOOKING_NOT_FOUND` 404; 200+empty for known unamended booking; 500 on DB error |
| `src/main.py` | MODIFIED — `amendments_router` registered; `"amendments"` tag added |
| `tests/test_amendments_router_contract.py` | NEW — 20 tests, Groups A–F |

## Notes

- Two DB queries are made only when the first (BOOKING_AMENDED) query returns empty: a lightweight existence check `SELECT booking_id LIMIT 1` determines 200-empty vs 404.
- This avoids penalising the common "has amendments" path with an extra query.

## Result

**2305 tests pass, 2 skipped.**
No Supabase schema changes. No migrations. No `booking_state` reads or writes.
