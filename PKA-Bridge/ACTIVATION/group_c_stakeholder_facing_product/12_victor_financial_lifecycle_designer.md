# Activation Memo: Victor — Financial Lifecycle Designer

**Phase:** 973 (Group C Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (src/adapters/ota/payment_lifecycle.py, reconciliation_model.py, src/api/checkout_settlement_router.py, checkin_settlement_router.py, deposit_settlement_router.py, financial_writer_router.py, financial_router.py, src/services/financial_writer.py, artifacts/supabase/schema.sql)
**Builds on:** Group A (financial isolation invariant, cash_deposits convergence, settlement engine), Group B (cleaner readiness gate, property status lifecycle)

---

## 1. What in the Current Real System Belongs to This Domain

Victor's domain is the financial lifecycle — money moving through states over time. The real system has:

- **7-state payment lifecycle** (`payment_lifecycle.py`): GUEST_PAID, OTA_COLLECTING, PAYOUT_PENDING, PAYOUT_RELEASED, RECONCILIATION_PENDING, OWNER_NET_PENDING, UNKNOWN — with deterministic decision rules
- **booking_financial_facts**: Append-only projection with source_confidence tiers (FULL, PARTIAL, ESTIMATED, OPERATOR_MANUAL). Multiple rows per booking (one per event). Financial isolation invariant from booking_state
- **Deposit lifecycle**: Collection at check-in (`cash_deposits` INSERT) → hold → settlement at checkout (draft → calculated → finalized → cash_deposits UPDATE)
- **Settlement engine**: Auto electricity deduction from meter delta. Manual damage/misc deductions. Finalize locks amounts and updates cash_deposits status (returned/forfeited)
- **Reconciliation model** (`reconciliation_model.py`): Discovery-only layer with 7 finding types. READ-ONLY — never modifies data
- **Payout computation**: Calculated on-demand with management fee deduction. NOT persisted — no payouts table
- **Financial reporting**: Per-booking facts, confidence reports, enrichment endpoint, per-property aggregation

## 2. What Appears Built

- **Payment lifecycle state machine (7 states, 6 rules)**: Fully deterministic decision tree in `payment_lifecycle.py`. Priority-ordered: (1) CANCELED → RECONCILIATION_PENDING, (2) no price data → UNKNOWN, (3) PARTIAL + no net → PAYOUT_PENDING, (4) net available → OWNER_NET_PENDING, (5) FULL + CREATED → GUEST_PAID, (6) fallback → UNKNOWN. Each booking gets exactly one state derived from its financial facts and event data.

- **booking_financial_facts (append-only, multi-row)**: Schema confirmed in `artifacts/supabase/schema.sql`. Columns: booking_id, tenant_id, provider, total_price, currency, ota_commission, taxes, fees, net_to_property, source_confidence, raw_financial_fields (JSONB), event_kind, recorded_at. No UNIQUE constraint on booking_id — intentionally append-only (multiple events per booking). Written by `financial_writer.py` after BOOKING_CREATED/AMENDED events.

- **Deposit lifecycle (collection → hold → settlement)**:
  - **Collection (Phase 964)**: `checkin_settlement_router.py` INSERT to cash_deposits with status='collected', deterministic id = sha256("DEP:{booking_id}:{now}")[:16], refund_amount initialized to full amount
  - **Settlement calculation (Phase 961)**: `checkout_settlement_router.py` reads cash_deposit, auto-creates electricity deduction from meter delta (opening - closing × rate_kwh), creates `deposit_deductions` records, updates `booking_settlement_records`
  - **Settlement finalization (Phase 961)**: Updates cash_deposits: if refund_amount > 0 → status='returned'; if retained_amount > 0 → status='forfeited'. Terminal states — no further writes
  - **Manual deposit (Phase 687)**: `deposit_settlement_router.py` allows manual deposit CRUD for admin/financial-capability users

- **Settlement authorization model**: Role guards by operation: write/capture (admin, ops, worker, checkin, checkout), add deductions (admin, ops, checkout), finalize (admin, ops, worker, checkout), void (admin only), read admin settlement (admin, manager). Checkout date eligibility gate: workers must satisfy date check or early_checkout_approved flag.

- **Reconciliation model (Phase 89, discovery-only)**: 7 finding types (BOOKING_MISSING_INTERNALLY, STATUS_MISMATCH, DATE_MISMATCH, FINANCIAL_FACTS_MISSING, FINANCIAL_AMOUNT_DRIFT, PROVIDER_DRIFT, STALE_BOOKING). Read-only — never writes to booking_state. Corrections require re-ingestion via standard pipeline. Phase 97 implementation pending.

- **Financial enrichment (Phase 470)**: `/financial/enrich` re-extracts facts for PARTIAL confidence bookings. Append-only — new row if confidence improved. Confidence report endpoint shows FULL/PARTIAL/ESTIMATED/OPERATOR_MANUAL distribution by provider.

- **Management fee calculation**: `net_payout = total_gross - (total_gross × mgmt_fee_pct / 100)`. Default 15%. Calculated at statement generation time, not persisted.

## 3. What Appears Partial

- **Deposit duplication guard is NOT structurally enforced**: The `cash_deposits` table does NOT have a UNIQUE constraint on (booking_id, tenant_id). The deposit ID uses `sha256("DEP:{booking_id}:{now}")[:16]` — the `{now}` component means two calls at different times produce different IDs. If the check-in deposit endpoint is called twice for the same booking, two deposit records are created. **This partially resolves open question #1** — the duplication guard is NOT structurally proven. The guard depends entirely on frontend/workflow discipline (the wizard advances past the deposit step and doesn't allow re-submission).

- **Settlement authorization is role-based but not always capability-gated**: Settlement endpoints use role guards (admin, ops, worker, checkout) but do NOT use `require_capability("financial")` for most operations. The financial capability guard protects the financial reporting endpoints and manual payment/payout endpoints. Settlement calculation and finalization are protected by role + checkout date eligibility, not by capability delegation. **This partially resolves open question #2** — settlement endpoints are authenticated and role-restricted, but the settlement mutation path (calculate, finalize) doesn't require explicit financial capability.

- **Reconciliation is discovery-only**: The model is defined (7 finding types with severity levels) but the implementation that actually runs reconciliation against OTA data (Phase 97) is not yet built. The system can detect discrepancies in theory but cannot surface them in practice.

## 4. What Appears Missing

- **No payouts table**: Payout is calculated on-demand but never stored. The `financial_writer_router.py` explicitly says "Full payout persistence is a deferred feature." Owner can see computed payout but no audit trail exists of payouts actually made.

- **No stale payment alerting**: The reconciliation model defines STALE_BOOKING (no update in 30+ days), but no automated detection or alerting is active. Payments can remain in OTA_COLLECTING indefinitely without any system-level flag.

- **No financial correction workflow**: If an OTA amends a payment after recording, no structured amendment flow exists. The append-only model means a new row can be added with corrected data (via enrichment or manual entry), but there's no explicit "correction" event type that links the correction to the original.

- **No commission edge case handling for direct bookings**: Commission calculation assumes OTA commission exists. Direct bookings (no OTA) or zero-commission bookings need a defined path — whether management fee is calculated on gross or net.

## 5. What Appears Risky

- **Deposit duplication is a live risk**: Two deposit records for the same booking would cause settlement to read the wrong one (or fail). The `_get_cash_deposit_id()` function in checkout_settlement_router reads "the" deposit — if multiple exist, it likely returns the first match. The second deposit would be orphaned and the refund amount would be wrong.

- **Management fee is ephemeral**: Calculated at statement time, not stored. If the fee percentage changes, past statements re-generated at the new rate would show different numbers. No versioning or snapshot.

- **Settlement finalization is the ONLY cross-table side effect**: The settlement engine's explicit design ("NEVER writes to event_log, booking_financial_facts, or booking_state") means finalization only updates cash_deposits. This is intentionally narrow but means financial data pipelines (booking_financial_facts) never reflect deposit outcomes. The owner statement must independently look up deposit status.

**Open question impact — checkout canonicality (#3)**: The settlement engine is intentionally outside the event-sourced domain. Checkout writes to booking_state directly (bypasses apply_envelope), and settlement writes to cash_deposits directly. Both are direct writes. If this architectural pattern is questioned, the entire financial settlement layer is affected — not just checkout.

## 6. What Appears Correct and Worth Preserving

- **Append-only financial facts**: Never mutate existing rows. New events append new rows. This provides a complete audit trail and prevents silent data corruption.
- **Source confidence tiers**: FULL/PARTIAL/ESTIMATED/OPERATOR_MANUAL with worst-tier-wins rollup. Honest about data quality.
- **Financial isolation invariant**: booking_financial_facts is never co-mingled with booking_state. Settlement explicitly states it never writes to financial_facts.
- **7-state payment lifecycle**: Deterministic, priority-ordered. Every booking gets exactly one state. No ambiguity.
- **Reconciliation as read-only discovery**: The model never writes corrections directly. All fixes go through the standard pipeline. This prevents reconciliation from becoming a data corruption vector.
- **Settlement terminal states**: 'returned' and 'forfeited' are terminal. No further writes allowed. Prevents double-refund or double-forfeit.

## 7. What This Role Would Prioritize Next

1. **Add UNIQUE constraint on cash_deposits (booking_id, tenant_id)**: Structurally prevent duplicate deposits. Requires data migration check first.
2. **Create payouts table**: Record each payout as a committed record with snapshot of amounts, fee rate, and timestamp.
3. **Add management fee versioning**: Store the applied fee rate alongside each statement/payout record.
4. **Build reconciliation Phase 97**: Wire the discovery model to actual OTA comparison and surface findings via admin API.

## 8. Dependencies on Other Roles

- **Miriam**: Victor defines the financial lifecycle; Miriam presents it to owners. If the lifecycle has gaps, owner trust erodes.
- **Elena (Group A)**: Elena verifies data consistency. Financial facts must match source events.
- **Ravi (Group A)**: Ravi maps service flows that include financial steps. The deposit lifecycle crosses Ravi's check-in and checkout flows.
- **Daniel (Group A)**: Daniel confirms whether settlement endpoints should have capability guards (financial) in addition to role guards.
- **Oren**: Oren reviews whether financial data is exposed beyond trust boundaries. Deposit amounts visible to workers need review.

## 9. What the Owner Most Urgently Needs to Understand

The financial lifecycle has a sophisticated architecture — 7-state payment lifecycle, append-only facts with confidence tiers, a working settlement engine, and a reconciliation model. The honesty rule (OTA_COLLECTING excluded from net) is a standout feature.

Three structural gaps need attention:

1. **Deposit duplication has no structural guard**: No UNIQUE constraint prevents two deposit records per booking. The system relies on workflow discipline. At scale, this will produce errors.

2. **Payouts don't persist**: The most critical financial operation (paying the owner) has no audit trail. This must be fixed before scaling.

3. **Settlement is authenticated but not capability-gated**: Workers with role access can finalize settlements without explicit financial capability delegation. Whether this is intentional (workers handle deposits operationally) or a gap (should require financial capability) is a design question that needs a deliberate answer.
