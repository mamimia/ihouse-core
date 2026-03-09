# Phase 121 — Owner Statement Generator (Ring 4)

**Status:** Closed
**Prerequisite:** Phase 120 (Cashflow / Payout Timeline)
**Date Closed:** 2026-03-09

## Goal

Enhance the basic Phase 101 owner statement endpoint into a full Ring 4 financial surface.
The endpoint now returns per-booking line items with check-in/out, OTA, gross commission,
net-to-property, payout lifecycle status, and epistemic tier (A/B/C) on every monetary figure.
A configurable management fee is deducted from the owner net total.
A PDF export path (`?format=pdf`) returns a plain-text statement body.
Role-scoping: owner accounts see only their own properties (property_id filter enforced).

All data sourced exclusively from `booking_financial_facts`. Never reads `booking_state`.

## Invariant (if applicable)

- All financial reads from `booking_financial_facts` ONLY — never `booking_state` (Phase 116).
- OTA_COLLECTING NEVER counted as received payout (Phase 120).
- Epistemic tier: FULL→A, ESTIMATED→B, PARTIAL→C. Worst tier wins in aggregated totals.
- Management fee is applied AFTER OTA commission deduction (on net_to_property).
- PDF format returns `text/plain` — no external PDF library dependency.
- Deduplication: most-recent `recorded_at` per `booking_id` (Phase 116 dedup rule).
- Tenant isolation enforced at DB level (`.eq("tenant_id", tenant_id)`).

## Design / Files

| File | Change |
|------|--------|
| `src/api/owner_statement_router.py` | MODIFIED — enhanced with line items, management fee, epistemic tier, PDF export, proper property_id DB filter |
| `tests/test_owner_statement_phase121_contract.py` | NEW — contract tests Groups A–G, ~40 tests |
| `docs/archive/phases/phase-121-spec.md` | NEW (this file) |

## Result

**~2900 tests pass, 2 pre-existing SQLite skips.**
No DB schema changes. All reads from `booking_financial_facts` only.
