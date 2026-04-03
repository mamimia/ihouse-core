# Audit Result: 11 — Miriam (Owner Experience Strategist)

**Group:** C — Stakeholder-Facing Product
**Reviewer:** Miriam
**Closure pass:** 2026-04-04
**Auditor:** Antigravity

---

## Closure Classification Table

| Item | Closure State |
|---|---|
| Owner portal with real financial data | ✅ **Proven resolved** — confirmed complete |
| Statement honesty rule (OTA_COLLECTING excluded from net) | ✅ **Proven resolved** — Phase 120 correct |
| PDF generation, multilingual | ✅ **Proven resolved** — confirmed correct |
| Visibility flags — app-level filtering (not SQL-level) | 🔵 **Intentional future gap** — lower-priority refactor; see below |
| No payout persistence | 🔵 **Intentional future gap** — documented deferral; see below |
| Management fee not stored/versioned | 🔵 **Intentional future gap** — schema decision required; see below |

---

## Closure Detail: Owner Visibility Filtering

**Item: 8 visibility flags enforced at application layer, not SQL layer**

Confirmed: `owner_portal_v2_router.py` uses `if visible.get(flag)` guards before each DB query. The DB is never queried for disabled sections. Data scoping is correct. The claim that this is "only app-level" is overstated — there is no data leak path. The APPLICATION is the correct enforcement point for these product-configurable visibility flags.

**Addendum from Sonia (06) audit depth check:** Sonia's audit confirmed query-level gating for the admin-facing owner visibility view. The behavioral result is correct.

**Closure state: Intentional future gap — but LOW risk, NOT fragile**

Moving to SQL-level filtering (conditional JOIN clauses that return no rows for disabled sections) is architecturally cleaner but provides no safety improvement — the current pattern never executes the query. The refactor belongs in a code-quality sprint when the portal layer is being reworked. Not a bug.

---

## Closure Detail: Payout Persistence

**Item: Financial payouts are computed on-demand but never recorded**

Proven: `financial_writer_router.py` explicitly documents: *"Full payout persistence is a deferred feature."* No `payouts` table exists. Payouts are correct in computation but leave no audit trail.

**Closure state: Intentional future gap — not a bug-level fix for this audit pass**

**Reason this cannot be patched in isolation:**
- A `payouts` table requires a schema migration (new table with `applied_fee_rate`, `snapshot_amounts`, `disbursed_at`, `disbursed_by`, `booking_id`, `tenant_id`, `property_id`)
- The write path requires updating `financial_writer_router.py` to INSERT on each payout calculation completion
- The `applied_fee_rate` must be captured AT THE MOMENT of computation, not re-read later
- This entire flow needs design and test — it is not a one-line fix

**When to fix:** Before first live multi-property tenant begins receiving regular payouts and needs an auditable record. This is a pre-scale financial infrastructure item.

---

## Closure Detail: Management Fee Versioning

**Item: Management fee percentage read from config at statement time, not stored with statement**

Proven: `management_fee_pct` is a query parameter re-read from config each time a statement is generated. If the fee rate changes between generation runs, historical statements produce different numbers.

**Closure state: Intentional future gap — schema decision required before code can change**

**Reason this cannot be patched in isolation:**
Options for the fix:
1. Add `applied_management_fee_pct` column to `owner_statements` table (requires migration)
2. Add a `management_fee_history` table with effective-date ranges (requires migration + policy)
3. Snapshot the rate into `booking_financial_facts` at write time (changes the write path)

All three require a product decision about which approach to use. Applying one without the decision risks schema churn. **No code change until approach is decided.**

**When to fix:** Before first live statement delivery to an owner who has experienced a fee rate change.
