# Title

Cash Deposits Are Architecturally Isolated From Financial Reporting — By Declared Design, Not Accident

# Why this matters

An operator using iHouseCore to manage properties collects security deposits at check-in. Those deposits — sometimes exceeding the nightly rate — are tracked in a `cash_deposits` table with a full lifecycle (collected → deductions → returned/forfeited). The financial dashboard, owner portal, and payout calculations all read exclusively from `booking_financial_facts`. These two systems do not connect. A property that collected 30,000 THB in deposits over a month has a financial report that shows zero of that amount. This is not an accidental gap — the router invariant explicitly declares "financial integration is deferred." But the practical consequence for any operator using the financial dashboard as a complete picture of funds handled is significant and non-obvious.

# Original claim

Cash deposits collected during check-in are intentionally isolated from `booking_financial_facts`, making them invisible to all financial reporting.

# Final verdict

PROVEN

# Executive summary

The `deposit_settlement_router.py` module invariant states: "This router NEVER writes to event_log or booking_financial_facts. Deposit records are independent — financial integration is deferred." Direct reading confirms this — all deposit writes go to `cash_deposits` and `deposit_deductions` tables only. The financial reporting layer (`financial_router.py`, `owner_portal_v2_router.py`, `financial_dashboard_router.py`) reads exclusively from `booking_financial_facts`. There is no join, no sync, no trigger connecting these systems. The `cash_deposits` table is a separate operational record with no path into financial reporting.

# Exact repository evidence

- `src/api/deposit_settlement_router.py` lines 17–20 — module invariant declaration
- `src/api/deposit_settlement_router.py` lines 87–89 — `db.table("cash_deposits").insert(row)` (only table written)
- `src/api/financial_router.py` lines 84–92 — reads `booking_financial_facts` only
- `src/api/owner_portal_v2_router.py` lines 161–173 — financial summary from `booking_financial_facts`
- `src/services/financial_writer.py` lines 44–56 — `record_manual_payment` upserts `booking_financial_facts`
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 554–566 — `POST /deposits` called during check-in

# Detailed evidence

**The invariant — explicit in source:**
```python
"""
Phases 687–690 — Deposit Settlement & Checkout Completion
...
Invariant:
    This router NEVER writes to event_log or booking_financial_facts.
    Deposit records are independent — financial integration is deferred.
"""
```
"Deferred" is deliberate language — it acknowledges the integration is planned but explicitly states it is not built. This is not a developer oversight; it is a documented architectural decision to ship deposit operations before completing the financial pipeline connection.

**Deposit collection write path:**
```python
row = {
    "id": deposit_id,
    "booking_id": booking_id,
    "tenant_id": tenant_id,
    "amount": float(amount),
    "currency": currency,
    "status": "collected",
    "collected_by": collected_by,
    "collected_at": now,
    "notes": notes,
    "refund_amount": float(amount),
    "created_at": now,
}
result = db.table("cash_deposits").insert(row).execute()
```
One table. One write. `booking_financial_facts` is not touched.

**The full deposit lifecycle (all writes stay in deposit tables):**
- `POST /deposits` → `cash_deposits` (status: "collected")
- `POST /deposits/{id}/deductions` → `deposit_deductions` (subtracted from `cash_deposits.refund_amount`)
- `DELETE /deposits/{id}/deductions/{id}` → `deposit_deductions` (deleted, refund recalculated)
- `POST /deposits/{id}/return` → `cash_deposits` (status: "returned")
- Settlement GET → reads `cash_deposits` + `deposit_deductions`

None of these writes touch `booking_financial_facts`.

**Financial reporting reads only `booking_financial_facts`:**
```python
# financial_router.py
result = db.table("booking_financial_facts").select("*").eq("booking_id", booking_id)...

# owner_portal_v2_router.py
fin = db.table("booking_financial_facts").select("total_price, management_fee, net_to_property")
      .eq("property_id", property_id).execute()
summary["financial"] = {
    "total_revenue": sum(f.get("total_price", 0) for f in fin_data),
    ...
}
```
Zero references to `cash_deposits` in any financial reporting endpoint.

**What `booking_financial_facts` contains:**
OTA-sourced or manually-recorded financial facts: `total_price`, `ota_commission`, `taxes`, `fees`, `net_to_property`, `currency`, `source_confidence`. These are booking-level revenue facts. They do not include deposits.

**Quantifying the gap:**
In a typical short-term rental scenario:
- Booking revenue: 3,000 THB/night × 3 nights = 9,000 THB → in `booking_financial_facts`
- Security deposit: 10,000 THB → in `cash_deposits`
- Financial report shows: 9,000 THB
- Actual cash collected at check-in: 19,000 THB
- Cash handled that is invisible to financial reporting: 52.6% of total

The gap grows with deposit-to-nightly-rate ratio and is worst for shorter stays with fixed deposits.

**The `record_manual_payment` escape hatch:**
`services/financial_writer.py` provides `record_manual_payment` which can write to `booking_financial_facts` with `payment_type = "manual_adjustment"`. This is the mechanism an operator could use to manually record deposit transactions into the financial system — but it requires knowing this workaround exists, it requires manual action per deposit, it creates financial fact rows with `source_confidence` of whatever the caller sets (likely `OPERATOR_MANUAL`), and it is completely disconnected from the `cash_deposits` lifecycle.

**The `financial/enrich` endpoint:**
`POST /financial/enrich` re-extracts financial facts for PARTIAL confidence bookings using the OTA adapter pipeline. This enrichment process reads from `booking_financial_facts` raw fields only — it has no path to discover deposit data in `cash_deposits`.

# Contradictions

- The module header says "Deposit records are independent — financial integration is deferred." The word "deferred" implies a plan. No evidence of that plan exists in the current code — no migration, no FK, no scheduled task, no mention in roadmap documentation.
- The owner portal v2 financial summary is presented as a complete financial picture per property. For properties with deposits, it is materially incomplete.
- `generate_payout_record` (financial_writer.py) sums `total_gross` from `booking_financial_facts` for a period. The payout calculation is based on booking revenue only — deposits are excluded from payout math. If a deposit was forfeited (not returned), that amount is never included in the owner's net calculation.
- The deposit lifecycle has a `status` field with values (`collected`, `returned`). A forfeited deposit (deposit collected but never returned, presumably because of damage) has no status — it stays at `collected`. The system never explicitly marks a deposit as forfeited. There is no path from deposit status to financial reconciliation.

# What is confirmed

- All deposit operations write to `cash_deposits` and `deposit_deductions` only.
- No financial reporting endpoint reads from `cash_deposits`.
- The isolation is declared intentional via the module invariant.
- "Deferred" integration has no visible implementation timeline in the codebase.
- Forfeited deposits (never returned) stay in `status: "collected"` with no explicit forfeiture state.

# What is not confirmed

- Whether the `cash_deposits` table is exposed via any API that operators can use for deposit-specific reporting.
- Whether the owner portal has any planned surface for deposit history.
- Whether any financial report aggregation in `financial_dashboard_router.py` (not fully read) joins or references deposit data.
- Whether a `deposit_forfeited` status or a separate `deposit_settlements` table exists in a migration that was not read.

# Practical interpretation

From an operator's perspective: the cash collected at a property is split across two systems that never talk to each other. When reviewing finances for a property, the operator sees booking revenue in the financial dashboard and must separately track deposit flows through a deposit-specific surface (if one exists) or through manual DB queries. There is no single screen or report that shows total cash inflows.

For owner payouts: an owner's payout calculation excludes deposit activity entirely. A forfeited deposit — the most financially significant deposit event, where the owner retains the security money — does not flow into the owner's net revenue calculation.

For reconciliation: end-of-month cash reconciliation requires cross-referencing `cash_deposits` data against `booking_financial_facts` data manually. The system provides no integrated view.

# Risk if misunderstood

**If financial reports are trusted as complete:** Property-level cash handling is underreported. Month-end reconciliation will show discrepancies between cash on hand and reported revenue that cannot be explained without knowing about the deposit isolation.

**If deposits are assumed to be included in payout calculations:** Owner payouts may be incorrect. A month with several large forfeited deposits (property damage) would show the same payout calculation as a month with zero forfeitures — the forfeited deposits add nothing to the net calculation.

**If the `record_manual_payment` workaround is used:** Manual payment records entered via `POST /admin/financial/payment` will mix with OTA-sourced financial facts in `booking_financial_facts`. The `source_confidence` field would be `OPERATOR_MANUAL` for deposit-related entries, but the total revenue sum in the financial dashboard would include them — creating an inconsistency between the deposit management system records and the financial dashboard.

# Recommended follow-up check

1. Read `src/api/financial_dashboard_router.py` fully — check whether it reads or joins `cash_deposits` anywhere (not confirmed in current reading).
2. Search all migrations for a `deposit_forfeited` status or any FK between `cash_deposits` and `booking_financial_facts`.
3. Determine whether there is a `/deposits` read endpoint visible to owners or managers — if so, deposit history is accessible but just not integrated into financial reporting.
4. Verify whether `generate_payout_record` is expected to include deposit forfeitures in the net payout — if so, this is a product gap, not just an implementation gap.
