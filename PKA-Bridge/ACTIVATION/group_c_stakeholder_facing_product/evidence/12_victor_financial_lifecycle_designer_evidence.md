# Evidence File: Victor — Financial Lifecycle Designer

**Paired memo:** `12_victor_financial_lifecycle_designer.md`
**Evidence status:** Strong structural evidence from payment lifecycle, settlement routers, and schema. Deposit duplication risk confirmed with exact code. Settlement authorization model fully traced.

---

## Claim 1: 7-state payment lifecycle with deterministic decision rules

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/adapters/ota/payment_lifecycle.py` — 7 states: GUEST_PAID, OTA_COLLECTING, PAYOUT_PENDING, PAYOUT_RELEASED, RECONCILIATION_PENDING, OWNER_NET_PENDING, UNKNOWN
- Same file: 6 priority-ordered decision rules: (1) CANCELED → RECONCILIATION_PENDING, (2) no price data → UNKNOWN, (3) PARTIAL + no net → PAYOUT_PENDING, (4) net available → OWNER_NET_PENDING, (5) FULL + CREATED → GUEST_PAID, (6) fallback → UNKNOWN

**What was observed:** The lifecycle state machine is fully deterministic. Each booking's financial facts and event data produce exactly one state through a priority-ordered decision tree. No ambiguity or dual-state conditions. The logic is a pure function of inputs — no side effects.

**Confidence:** HIGH

**Uncertainty:** None. The code is explicit and self-contained.

---

## Claim 2: booking_financial_facts is append-only with no UNIQUE constraint on booking_id

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `artifacts/supabase/schema.sql` — booking_financial_facts table columns: booking_id, tenant_id, provider, total_price, currency, ota_commission, taxes, fees, net_to_property, source_confidence, raw_financial_fields (JSONB), event_kind, recorded_at. NO UNIQUE constraint on booking_id.
- File: `src/services/financial_writer.py` — INSERT operations only. No UPDATE or DELETE on booking_financial_facts. New events produce new rows.

**What was observed:** The table is intentionally append-only. Multiple rows per booking represent different events (BOOKING_CREATED, BOOKING_AMENDED, enrichment). The financial_writer only ever INSERTs. This creates a full audit trail.

**Confidence:** HIGH

**Uncertainty:** None. The append-only pattern is confirmed by both schema (no UNIQUE on booking_id) and code (INSERT only).

---

## Claim 3: cash_deposits has NO UNIQUE constraint on (booking_id, tenant_id) — DEPOSIT DUPLICATION IS STRUCTURALLY POSSIBLE

**Status:** DIRECTLY PROVEN — ELEVATES OPEN QUESTION #1

**Evidence basis:**
- File: `artifacts/supabase/schema.sql` — cash_deposits table: id (deterministic sha256), booking_id, tenant_id, amount, currency, status, refund_amount, retained_amount, recorded_at. NO UNIQUE constraint on (booking_id, tenant_id).
- File: `src/api/checkin_settlement_router.py` — Deposit ID generated as `sha256("DEP:{booking_id}:{now}")[:16]`. The `{now}` component means two calls at different timestamps produce different IDs. No pre-check for existing deposit before INSERT.

**What was observed:** If the check-in deposit endpoint is called twice for the same booking (e.g., network retry, wizard re-entry, double-tap), two deposit records are created with different IDs (because the timestamp differs). No database constraint prevents this. No application-level guard (SELECT before INSERT) was found. The duplication guard relies entirely on the frontend wizard not allowing re-submission of the deposit step.

**Confidence:** HIGH

**Uncertainty:** None regarding the structural gap. The practical frequency depends on frontend behavior, but the structural protection is absent.

---

## Claim 4: Settlement authorization is role-based but NOT capability-gated — PARTIALLY RESOLVES OPEN QUESTION #2

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/checkout_settlement_router.py` — Settlement endpoints use role guards: write/capture (admin, ops, worker, checkin, checkout), add deductions (admin, ops, checkout), finalize (admin, ops, worker, checkout), void (admin only), read admin settlement (admin, manager). No `require_capability("financial")` on settlement mutation endpoints.
- File: `src/api/financial_router.py` — Financial reporting endpoints DO use `require_capability("financial")` for access control
- File: `src/api/deposit_settlement_router.py` — Manual deposit CRUD requires admin or financial-capability users

**What was observed:** Two distinct authorization patterns exist:
1. Financial reporting + manual deposit operations → capability-gated via `require_capability("financial")`
2. Settlement calculation + finalization → role-gated only (admin, ops, worker, checkout roles)

The settlement mutation path (calculate, finalize) does not require explicit financial capability delegation. A worker with checkout role can finalize a settlement without the financial capability. Whether this is intentional (workers handle deposits operationally at the property) or a gap (should require financial delegation) is a design question.

**Confidence:** HIGH

**Uncertainty:** Whether the role-only pattern is intentional or an oversight. The two patterns coexist without documentation explaining the distinction.

---

## Claim 5: Deposit lifecycle — collection → hold → settlement → terminal states

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/checkin_settlement_router.py` — Collection: INSERT to cash_deposits with status='collected', refund_amount initialized to full deposit amount
- File: `src/api/checkout_settlement_router.py` — Settlement: reads deposit, creates deduction records (auto electricity from meter delta, manual damage/misc), updates booking_settlement_records. Finalization: updates cash_deposits status to 'returned' (if refund > 0) or 'forfeited' (if retained > 0). Terminal states — no further writes allowed after finalization.

**What was observed:** The deposit lifecycle is complete from collection through settlement to terminal status. The auto-electricity deduction calculates from meter delta (opening - closing × rate_kwh). Terminal states are enforced — finalized deposits cannot be modified.

**Confidence:** HIGH

**Uncertainty:** None for the happy path. Edge cases (partial forfeit + partial return, zero-amount deposits) were not specifically traced.

---

## Claim 6: Reconciliation model is discovery-only (Phase 89) — never writes corrections

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/adapters/ota/reconciliation_model.py` — 7 finding types: BOOKING_MISSING_INTERNALLY, STATUS_MISMATCH, DATE_MISMATCH, FINANCIAL_FACTS_MISSING, FINANCIAL_AMOUNT_DRIFT, PROVIDER_DRIFT, STALE_BOOKING. Each with severity levels. The model is READ-ONLY — it discovers discrepancies but never writes corrections to booking_state or booking_financial_facts.

**What was observed:** Reconciliation produces findings (discrepancy reports) but corrections must go through the standard ingestion pipeline. The model explicitly avoids being a write path. Phase 97 (actual execution against OTA data) is referenced but not implemented.

**Confidence:** HIGH

**Uncertainty:** None regarding the model. The Phase 97 implementation gap means the model is defined but not yet operational.

---

## Claim 7: Payout computes but does NOT persist — no payouts table

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/financial_writer_router.py` — Explicit statement: "this is a point-in-time snapshot, not a committed payout record." Payout computation reads booking_financial_facts, applies management fee deduction, returns computed amounts.
- File: `artifacts/supabase/schema.sql` — No `payouts` table exists in schema
- File: `src/services/financial_writer.py` — Financial writer INSERTs to booking_financial_facts only. No payout recording function.

**What was observed:** The payout endpoint is a read-compute-return path with no persistence. The computed payout amount is returned in the API response and exists only for that request. No historical record of payouts. No audit trail for money actually disbursed to owners.

**Confidence:** HIGH

**Uncertainty:** None. This is explicitly documented as a deferred feature in the code comments.

---

## Claim 8: Settlement explicitly never writes to event_log, booking_financial_facts, or booking_state

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/checkout_settlement_router.py` — Settlement endpoints write ONLY to: cash_deposits (status update), deposit_deductions (deduction records), booking_settlement_records (settlement summary). Explicit design invariant: settlement is outside the event-sourced domain.

**What was observed:** The settlement engine is intentionally isolated from the event-sourced booking lifecycle. It reads from booking data but writes only to its own tables. This means booking_financial_facts never reflects deposit outcomes directly — they must be joined separately.

**Confidence:** HIGH

**Uncertainty:** None. The isolation is by explicit design, confirmed in code comments.

---

## Claim 9: Source confidence tiers with worst-tier-wins rollup

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/services/financial_writer.py` — source_confidence values: FULL, PARTIAL, ESTIMATED, OPERATOR_MANUAL. Assigned during financial fact extraction based on data completeness.
- File: `src/api/owner_statement_router.py` — Statement generation includes overall_epistemic_tier that uses worst-tier-wins: if any booking in the statement has ESTIMATED confidence, the overall tier drops to ESTIMATED regardless of other bookings.

**What was observed:** The confidence system is honest end-to-end. Individual bookings carry their own confidence. The owner statement aggregates using worst-tier-wins, ensuring the overall confidence never overstates data quality.

**Confidence:** HIGH

**Uncertainty:** None.
