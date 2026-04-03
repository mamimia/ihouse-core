# Title

Cash Deposit Financial Isolation — Investigation Fully Confirmed; No Code Changes; Four Product Decisions Required Before Integration

# Related files

- Investigation: `INVESTIGATIONS/11_deposit_financial_isolation.md`
- Evidence: `EVIDENCE/11_deposit_financial_isolation.md`

# Original claim

`cash_deposits` is completely isolated from financial reporting. The `deposit_settlement_router.py` module invariant explicitly declares it never writes to `event_log` or `booking_financial_facts`. All financial reporting endpoints read from `booking_financial_facts` only. Deposits are invisible to every financial view.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict from implementation layer: Investigation is correct. Real issue. Intentional by declaration, but creates a material financial blind spot. No code changes — 4 product decisions needed.**

The isolation is proven completely. All four unconfirmed items from the investigation have been resolved.

**All 5 questions answered:**

**1. Does the deposit router truly write only to `cash_deposits` / `deposit_deductions`?**
Yes — confirmed completely. Full 433-line router (Phases 687–690) read end-to-end:

| Operation | Table written |
|-----------|-------------|
| `POST /deposits` (collect) | `cash_deposits` only |
| `POST /deposits/{id}/return` | `cash_deposits` only (status update) |
| `POST /deposits/{id}/deductions` | `deposit_deductions` + `cash_deposits.refund_amount` recalc |
| `DELETE /deposits/{id}/deductions/{id}` | `deposit_deductions` + `cash_deposits.refund_amount` recalc |
| `POST /bookings/{id}/checkout` | `bookings` table only (`status → "checked_out"`) |

The module invariant ("NEVER writes to `event_log` or `booking_financial_facts`") is not aspirational — it is accurate.

**2. Do all financial reporting endpoints read only from `booking_financial_facts`?**
Yes — confirmed completely. Zero references to `cash_deposits` in any financial reporting file:

| Endpoint | Source | Deposit data? |
|----------|--------|--------------|
| `financial_dashboard_router.py` | `booking_financial_facts` | ❌ None |
| `owner_portal_v2_router.py` financial summary | `booking_financial_facts` | ❌ None |
| `owner_statement_router.py` | `booking_financial_facts` | ❌ None |
| `generate_payout_record()` | `booking_financial_facts` | ❌ None |

Additionally: owners have no deposit surface at all. The owner portal (`/owner` page) has no deposit history, no deposit view, and no cross-link to deposit states. Deposit data is accessible only via `GET /deposits?booking_id=` to users with `require_capability("financial")` — admin or delegated managers only.

**3. Is this intentional?**
Yes — the word "deferred" in the module invariant is a specific engineering term: acknowledged but not yet built. However, no evidence of a plan for integration exists in the codebase:
- No migration connecting `cash_deposits` to `booking_financial_facts`
- No FK relationship between the tables
- No view, trigger, or scheduled task bridging them
- Zero `grep` results for `deposit_forfeited` anywhere in the codebase
- `cash_deposits.status` only has two reachable values: `"collected"` and `"returned"`

**Critical finding — no forfeited status exists:**
A deposit that is collected but never returned (because the guest caused damage and the operator kept it) stays permanently at `status: "collected"`. The system cannot distinguish:
- "Deposit outstanding, not yet settled" (guest still present or recently departed)
- "Deposit forfeited/retained" (damage occurred, operator keeping the deposit)

Both look identical in the database.

**4. Is the current behavior misleading?**
Yes — materially. What the financial dashboard shows per booking vs. what it permanently omits:

Visible: `total_price`, `ota_commission`, `net_to_property` (OTA-sourced) + `record_manual_payment` entries

Permanently omitted:
- Initial deposit collected at check-in
- Amount retained after deductions (the "kept" portion)
- Amount returned to guest
- Any forfeited deposit balance

Concrete example:
```
Booking revenue:        9,000 THB  → visible in financial dashboard
Security deposit:      10,000 THB  → invisible
Cash collected at property: 19,000 THB

Dashboard shows: 9,000 THB (52.6% of actual cash is invisible)
```

For damage incidents: a month with three 10,000 THB deposit forfeitures shows the same payout as a month with zero forfeitures. The forfeitures add nothing to the owner's financial picture.

**5. Four product decisions required (no code fix appropriate without these):**

**Decision A — Should forfeited deposits appear in owner payout calculations?**
If an operator retains a 10,000 THB deposit due to damage, should that appear as income in the payout statement?
- Yes → write a `booking_financial_facts` entry with `provider: "deposit_forfeiture"`, `total_gross: retained_amount` when a deposit is retained
- No → deposit forfeitures are outside the OTA revenue model; owner payouts reflect booking revenue only
The current system implicitly chose "no" by deferring. This must become an explicit product decision.

**Decision B — Should `cash_deposits` have a `forfeited` status?**
Current values: `"collected"` and `"returned"` only. A deposit kept due to damage has no end state.
At minimum needed (independent of Decision A):
- `"partially_returned"` — deposit with deductions + partial return
- `"forfeited"` — deposit never returned, intentionally retained

**Decision C — What deposit summary should managers and owners see?**
Currently the only deposit view is `GET /deposits?booking_id=` (per-booking, financial capability required). No per-property deposit summary, no period deposit report, no owner-facing deposit history exists. A summary endpoint (`GET /financial/deposits/summary?month=YYYY-MM&property_id=...`) would give visibility without requiring full financial integration.

**Decision D — Should deposit totals appear in the financial dashboard at all?**
- Option 1 (fully integrated): Add deposit data to `booking_financial_facts` — appears in dashboards alongside booking revenue. Requires handling OTA vs cash reconciliation differences.
- Option 2 (separate panel): Add a "Deposits" section to the financial dashboard reading from `cash_deposits` directly. Lower risk, preserves epistemic integrity of OTA revenue data.

**Capability guard structure confirmed correctly designed (not a bug):**
- All deposit write operations: `require_capability("financial")` ✅
- Photo comparison: no capability guard (operational, worker-facing) ✅
- Checkout completion: no capability guard (operational, worker-facing) ✅

**Changes made: None.**

# Verification reading

No additional repository verification read performed. The implementation response resolves all four items the investigation marked as unconfirmed: (1) full router write scope confirmed; (2) zero deposit references in financial files confirmed; (3) intentional/deferred confirmed; (4) no `deposit_forfeited` status anywhere — confirmed.

# Verification verdict

PARTIALLY RESOLVED

The investigation is fully confirmed. The finding stands: deposits are materially invisible to financial reporting. No code changes were made because four product decisions must precede any integration. The isolation is correct engineering; the missing reporting path requires deliberate product choices before it can be built.

# What changed

Nothing. No code was modified.

# What now appears true

- `cash_deposits` and `booking_financial_facts` are completely isolated with no FK, no migration bridge, no view, no trigger, and no code path connecting them.
- Deposits can represent the majority of cash handled at a property (e.g., 10,000 THB deposit on a 9,000 THB booking) and are completely invisible to every financial report, owner statement, and payout calculation.
- The `cash_deposits.status` field has no end state for "forfeited" — a retained deposit looks identical to a pending unsettled deposit indefinitely.
- Owners have zero deposit visibility in any surface of the system.
- Deposit data is accessible only to `admin` and capability-delegated managers via per-booking query.
- The "deferred" declaration in the module invariant was intentional but there is no evidence of any integration plan — no migration, no FK, no scheduled task, no architectural note beyond the invariant itself.

# What is still unclear

- **How many properties in production have active `cash_deposits` records** — and therefore how large the invisible cash pool is relative to reported financial data.
- **Whether any operator has manually been recording deposit forfeitures via `record_manual_payment`** as a workaround for the missing integration. If they have, those records exist in `booking_financial_facts` with `payment_type: "manual_adjustment"` — the workaround would be the only current path to surfacing deposit cash.
- **Whether the iCal-first operating mode means deposits are actually collected at this stage** — if the system is not yet handling physical check-ins at scale, the current blind spot may be pre-operational. Once check-ins with deposits begin in production, the gap becomes real.

# Recommended next step

**Keep open as a product backlog item requiring four explicit decisions.**

**Minimum viable path (if full integration is not ready):**

1. **Add `status` values `"partially_returned"` and `"forfeited"` to `cash_deposits`** — this is a data integrity fix independent of financial integration, and closes the "retained deposit looks like pending" ambiguity. Low risk, no financial reporting impact.

2. **Add a deposit summary endpoint** (`GET /financial/deposits/summary`) that reads `cash_deposits` directly and returns per-period, per-property deposit totals. This gives admin/manager visibility without requiring any `booking_financial_facts` integration.

3. **Decision A must come before building any financial integration** — whether forfeited deposits are "income" is a business model question that affects tax treatment, owner agreement terms, and the semantics of the financial dashboard.

4. **Do not integrate deposits into `booking_financial_facts` without first resolving the OTA/cash reconciliation differences** — OTA revenue and cash deposits have different booking-date semantics, currency handling, and commission structures. Merging them without a clear reconciliation model would corrupt the epistemic tier system already in place in `owner_statement_router.py`.
