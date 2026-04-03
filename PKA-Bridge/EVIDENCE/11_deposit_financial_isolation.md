# Claim

Cash deposits collected during check-in are intentionally isolated from the `booking_financial_facts` table, making them invisible to all financial reporting.

# Verdict

PROVEN

# Why this verdict

`src/api/deposit_settlement_router.py` contains an explicit architecture invariant in its module header: "This router NEVER writes to event_log or booking_financial_facts. Deposit records are independent — financial integration is deferred." Direct reading of the router confirms this — deposits are written to `cash_deposits` only. The `booking_financial_facts` table is the source for all financial reports, owner portal financials, and the financial dashboard. These two systems do not connect.

# Direct repository evidence

- `src/api/deposit_settlement_router.py` lines 17–20 — invariant declaration
- `src/api/deposit_settlement_router.py` lines 87–89 — `db.table("cash_deposits").insert(row)`
- `src/api/financial_router.py` — reads only from `booking_financial_facts`
- `src/api/owner_portal_v2_router.py` lines 161–173 — financial summary reads `booking_financial_facts`
- `ihouse-ui/app/(app)/ops/checkin/page.tsx` lines 554–566 — frontend collects deposit via `/deposits`

# Evidence details

**Router invariant (explicit in source):**
```python
Invariant:
    This router NEVER writes to event_log or booking_financial_facts.
    Deposit records are independent — financial integration is deferred.
```
This is not a gap discovered by reading between the lines. It is a declared architectural choice documented in the module header.

**Deposit write (cash_deposits only):**
```python
result = db.table("cash_deposits").insert(row).execute()
```
No corresponding write to `booking_financial_facts`, `event_log`, or any other financial table.

**Financial reporting reads `booking_financial_facts` only:**
All financial API endpoints read from `booking_financial_facts`. The owner portal financial summary reads from `booking_financial_facts`. Deposit amounts in `cash_deposits` are never joined or referenced.

**Practical gap:** A property with 3,000 THB/night and a 10,000 THB security deposit collects 13,000 THB at check-in. The financial system knows about 3,000 THB (from the booking financial facts). The 10,000 THB deposit is in `cash_deposits`. The owner portal shows 3,000 THB collected.

# Conflicts or contradictions

- "Financial integration is deferred" implies the connection is planned but not built. There is no migration, no FK, and no timeline for this integration in the visible code.
- The deposit system has a full lifecycle (collected → deductions → returned/forfeited) but that lifecycle has no effect on financial reporting.

# What is still missing

- Whether any planned migration creates a view or trigger that joins `cash_deposits` into financial reports.
- Whether the `cash_deposits` table has its own reporting surface accessible to owners or managers.

# Risk if misunderstood

If operators trust the financial dashboard to show total funds collected per property, deposits will be missing. Owner payouts calculated from `booking_financial_facts` will undercount total cash handled at the property.
