# Activation Memo: Miriam — Owner Experience Strategist

**Phase:** 973 (Group C Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (src/api/owner_portal_v2_router.py, owner_statement_router.py, admin_owners_router.py, financial_writer_router.py, ihouse-ui/app/(app)/owner/page.tsx, onboard_token_router.py)
**Builds on:** Group A (financial isolation invariant, booking_financial_facts), Group B (Sonia's 8 visibility flags, owner surface structure)

---

## 1. What in the Current Real System Belongs to This Domain

Miriam's domain is the owner-facing product: what property owners see, how financial data is presented, how trust is built through progressive transparency, and how the owner lifecycle works. The real system has:

- **Owner portal** (`/owner`): Single-page surface with portfolio summary metrics, per-property financial cards, statement drawer with line items, cashflow timeline, auto-refresh + SSE
- **Owner statement engine** (`owner_statement_router.py`): Per-booking line items with gross, commission, net, lifecycle status, epistemic confidence tier. PDF generation. Management fee calculation at statement time. **Honesty rule**: OTA_COLLECTING bookings shown but excluded from net totals
- **8 visibility flags** (`owner_portal_v2_router.py`): Toggle per owner per property. Application-level filtering (NOT SQL-level)
- **Owner entity model** (`admin_owners_router.py`): Separate `owners` table with optional `user_id` link to login account. Property-to-owner linkage via `property_owners` table with UNIQUE constraint
- **Owner onboarding**: Token-based via `access_tokens` (type: ONBOARD). Public validation + acceptance
- **Payout computation**: Calculated on-demand, NOT persisted. No payouts table exists

## 2. What Appears Built

- **Owner portal with financial reality**: `/owner/page.tsx` renders portfolio summary (properties count, total bookings, gross revenue, owner net), per-property cards (gross, commission, owner net), month selector, manual refresh + 60-second auto-refresh + SSE on "financial" channel. Statement drawer opens per property with per-booking line items and Download PDF / Send Email buttons.

- **Owner statement engine (Phase 120 honesty rule)**: `owner_statement_router.py` generates per-booking line items including: booking_id, provider (OTA), check_in/check_out dates, gross, OTA commission, net_to_property, lifecycle_status, epistemic_tier (A/B/C confidence). **Critical design**: OTA_COLLECTING bookings appear in line items for visibility but are **explicitly excluded from net calculations**. Only PAYOUT_RELEASED bookings count as received money. Summary includes management_fee_pct, management_fee_amount, owner_net_total, and overall_epistemic_tier (worst tier wins).

- **PDF statement generation**: `format=pdf` returns proper Content-Type: application/pdf via `generate_owner_statement_pdf()`. Language parameter for localization (en, th, he).

- **Owner property scoping (Phase 166)**: If caller has `role='owner'`, only allowed access to properties in `permissions.property_ids` array. Admin/manager unrestricted. 403 if owner tries to access property they don't own.

- **Owner entity management**: Admin can create owners, assign properties (batch), link to login account (Phase 1021, explicit admin action only), update, delete. `property_owners` table with UNIQUE(owner_id, property_id). Owner enrichment shows property_ids, property_count, linked_account details.

- **Cashflow timeline**: Owner portal fetches weekly expected inflows via `/cashflow/projection?period={month}`.

## 3. What Appears Partial

- **Visibility flag enforcement is application-level, not SQL-level**: The summary endpoint retrieves data from DB, then filters in application logic based on visibility flags. This means the backend queries all data regardless of visibility settings — filtering happens before the response is returned. It's honest (the response is correctly filtered) but not defense-in-depth (a bug in the filtering logic would expose everything). **This partially resolves open question #4 from the activation context** — enforcement exists but is not at the strongest possible layer.

- **Statement email delivery**: "Send by email" button exists in the frontend but is described as currently simulated/placeholder. The UI exists; the dispatch does not.

- **Owner onboarding journey**: Token validation endpoint exists (`onboard_token_router.py`), but the full onboarding UX (welcome state, first-visit empty state, explanation of what will appear) was not fully traced in the frontend. A new owner with zero bookings may see an empty portfolio with no guidance.

- **Management fee is calculated, not stored**: Fee percentage and amount are computed at statement generation time, not persisted. This means the fee for a given month could change retroactively if the percentage changes. No audit trail of applied fee rates.

## 4. What Appears Missing

- **No payout persistence**: Payout endpoint computes but does NOT persist. `financial_writer_router.py` explicitly states: "this is a point-in-time snapshot, not a committed payout record." No payouts table exists. The owner can see what they should receive but the system has no record of what was actually paid out. This is the #1 financial lifecycle gap.

- **No owner notification system**: No mechanism to notify owners when a new statement is available, when a payout is ready, or when a property status changes. The owner must log in and check.

- **No dispute/question resolution path**: If an owner sees a revenue number they don't understand, there's no in-portal mechanism to ask a question or flag a discrepancy. They must contact admin through external channels.

- **No owner-visible maintenance or task summary**: With default visibility (maintenance_reports OFF), owners have no visibility into property maintenance. Even with the flag ON, the actual query-level implementation of maintenance visibility was not traced.

## 5. What Appears Risky

- **Application-level visibility filtering**: A single filtering bug would expose all data to all owners. SQL-level enforcement (conditional JOINs based on flags) would be more robust.

- **Management fee not stored**: If admin changes the fee percentage after a statement was generated, re-generating the statement would show different numbers. No versioning or snapshot mechanism exists.

- **OTA_COLLECTING label ambiguity**: The statement shows lifecycle_status per booking. An owner seeing "OTA_COLLECTING" may not understand what it means. The honesty rule correctly excludes these from net totals, but the label needs UX treatment (tooltip, explanation text).

**Open question impact — deposit duplication guard**: If duplicate deposit records exist in `cash_deposits`, the owner's deposit-related line items in the statement could show incorrect amounts. Victor's financial trace is the authoritative input here.

**Open question impact — settlement endpoint authorization**: If settlement endpoints lack full capability guards, unauthorized finalization could produce incorrect deposit status in the owner's statement.

## 6. What Appears Correct and Worth Preserving

- **Honesty rule (Phase 120)**: OTA_COLLECTING bookings shown but excluded from net. This prevents over-promising. The owner sees what's expected but not counted as received. Correct financial design.
- **Epistemic confidence tiers**: Each booking shows A/B/C tier. Overall statement uses worst-tier-wins. The owner sees the confidence level of their financial data. Rare for property management platforms.
- **Owner property scoping**: Phase 166 correctly restricts owners to their own properties. Access control is per-request, not cached.
- **Progressive visibility defaults**: bookings/financial_summary/occupancy ON by default; maintenance/guest/task/worker/cleaning OFF. Correct progressive trust model.
- **Separate owners table with explicit user_id linkage**: Owners exist as business entities independent of login accounts. Linkage is intentional admin action (Phase 1021), not automatic. Correct separation of identity and entity.

## 7. What This Role Would Prioritize Next

1. **Add payout persistence**: Create a payouts table. Record each payout computation as a committed record with snapshot of amounts and fee rate at time of payout.
2. **Add first-visit empty state**: New owner with zero bookings should see "Your financial dashboard will populate once your first booking completes" with estimated timeline.
3. **Move visibility filtering to SQL level**: Add conditional JOINs or WHERE clauses in the Supabase query based on visibility flags, not just application-level filtering.
4. **Add statement email delivery**: Wire the "Send by email" button to actual delivery.

## 8. Dependencies on Other Roles

- **Victor**: Miriam's financial presentation depends entirely on Victor's lifecycle truth. If the payment state machine has gaps, the owner sees incorrect data.
- **Elena (Group A)**: Elena verifies data consistency. If booking_financial_facts drifts from truth, the owner statement is wrong.
- **Sonia (Group B)**: Sonia defines the owner surface structural scope. Miriam defines what the owner sees within it.
- **Oren**: Oren verifies that owner visibility controls actually protect data. If visibility filtering fails, owners see more than intended.

## 9. What the Owner Most Urgently Needs to Understand

The owner-facing product is more mature than expected. There is a working portal with real financial data, per-booking statements with honesty rules, PDF generation, epistemic confidence tiers, and progressive visibility controls. This is not a placeholder — it's a real owner-facing product surface.

Two things need immediate attention:

1. **Payouts don't persist**: The owner can see what they should receive, but the system has no record of what was actually paid out. This means there's no audit trail for the most important thing owners care about: "did the money arrive?"

2. **Visibility filtering is application-level**: It works correctly today, but a single bug would expose all data. Moving to SQL-level filtering adds defense-in-depth for a surface where data leaks directly affect trust.
