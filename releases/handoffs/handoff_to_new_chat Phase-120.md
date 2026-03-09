# Handoff to New Chat — Phase 120

**Date:** 2026-03-09  
**Context Level:** ~80% — switching chat now  
**Current Phase:** 120 — Cashflow / Payout Timeline (closed)  
**Last Closed Phase:** 120 — Cashflow / Payout Timeline  
**Next Objective:** Phase 121 — Owner Statement Generator (Ring 4)  
**Tests:** 2860 passing ✅ (2 pre-existing SQLite skips — unrelated)  
**Branch:** `checkpoint/supabase-single-write-20260305-1747`

---

## What Was Done This Session (Phases 118–120)

| Phase | Feature | Tests | Key File |
|-------|---------|-------|----------|
| 118 | Financial Dashboard API | 44 | `src/api/financial_dashboard_router.py` |
| 119 | Reconciliation Inbox API | 32 | `src/api/reconciliation_router.py` |
| 120 | Cashflow / Payout Timeline | 37 | `src/api/cashflow_router.py` |
| docs | Contextual Help Layer spec | — | `docs/future/contextual-help-layer.md` |

---

## Phase 121 — Next Objective

**Owner Statement Generator (Ring 4)**

Spec in `docs/core/roadmap.md`.  
The existing `owner_statement_router.py` (Phase 101) has a basic endpoint.  
Phase 121 enhances it with:

1. Per-booking line items (check-in/out, OTA, gross, commission, net)
2. Management fee deduction (configurable %)
3. Owner net total for period
4. Payout status per booking (lifecycle_status per line)
5. Epistemic tier (A/B/C) on every figure
6. PDF export — `GET /owner-statement/{property_id}?month=&format=pdf`
7. Role-scoped: owner accounts see only their properties

**Architecture rule:** All figures from `booking_financial_facts` only. Never `booking_state`.

---

## Financial API Ring Architecture (Completed)

All endpoints read from `booking_financial_facts` ONLY — never `booking_state`.

**Shared helpers in `financial_aggregation_router.py`:**
- `_fetch_period_rows(db, tenant_id, period)` — fetches all rows for month
- `_dedup_latest(rows)` — most-recent `recorded_at` per `booking_id`
- `_validate_period(period)` — returns `JSONResponse(400)` or `None`
- `_fmt(decimal)` — 2dp string
- `_to_decimal(val)` — safe Decimal with zero-guard
- `_canonical_currency(cur)` — normalizes or "OTHER"
- `_get_supabase_client()` — DB client

**Helpers in `financial_dashboard_router.py`:**
- `_tier(confidence)` → "A"/"B"/"C"
- `_worst_tier(tiers)` → worst from list
- `_monetary(val)` → string or None
- `_project_lifecycle_status(row, event_kind)` → lifecycle with graceful fallback

**Epistemic tier:** FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregated endpoints.

**Dedup rule:** most-recent `recorded_at` per `booking_id` — all Ring 1–3 routers use `_dedup_latest`.

---

## Key Invariants (Never Change)

- `apply_envelope` is the only write authority for canonical state
- `booking_id = "{source}_{reservation_ref}"` (Phase 36)
- `reservation_ref` normalized by `normalize_reservation_ref()` (Phase 68)
- `tenant_id` from JWT `sub` only — never from payload body (Phase 61)
- `booking_state` NEVER contains financial data (Phase 62)
- All financial reads from `booking_financial_facts` only (Phase 116)
- OTA_COLLECTING NEVER counted as received payout (Phase 120)

---

## Key Files

| File | Role |
|------|------|
| `docs/core/BOOT.md` | Boot sequence — read first |
| `docs/core/work-context.md` | Current state, invariants, key files |
| `docs/core/current-snapshot.md` | Full phase history table |
| `docs/core/roadmap.md` | Forward plan Phase 121–126+ |
| `src/api/financial_aggregation_router.py` | Ring 1 + shared helpers |
| `src/api/financial_dashboard_router.py` | Ring 2–3 + exported helpers |
| `src/api/reconciliation_router.py` | Reconciliation inbox |
| `src/api/cashflow_router.py` | Cashflow / payout timeline |
| `src/api/owner_statement_router.py` | Phase 101 basic — Phase 121 enhances this |
| `src/adapters/ota/owner_statement.py` | Statement builder — Phase 121 extends this |

---

## Open Items

| Item | Status |
|------|--------|
| 2 SQLite invariant test failures | Pre-existing, not blocking |
| Contextual Help Layer | Spec saved — future UI phase only |

---

*Context limit reached. Handoff complete. Open a new chat, read BOOT.md, start Phase 121.*
