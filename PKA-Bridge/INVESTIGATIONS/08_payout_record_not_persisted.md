# Title

Owner Payout Calculation Runs But Is Never Written to the Database

# Why this matters

`generate_payout_record` is the function responsible for computing what an owner is owed at the end of a rental period — the most financially significant output the system produces for owners. It queries real data, calculates gross revenue, deducts the management fee, and produces a complete payout record with a generated `payout_id`. But it then returns this record as a Python dict without writing it anywhere. There is no `INSERT` into any table. No payout history is accumulated. No owner statement is persisted. If a caller discards the return value, the calculation never happened at all.

# Original claim

Financial payout record generation does not persist — `generate_payout_record` calculates but does not write.

# Final verdict

PROVEN

# Executive summary

`src/services/financial_writer.py` defines three functions. Two of them — `record_manual_payment` and `update_fee_settings` (implied by the module header) — write to the database. The third, `generate_payout_record`, reads from `booking_financial_facts`, performs calculations, constructs a full payout dict with a UUID-based `payout_id`, and returns it. It does not call `db.table(...).insert(...)` or any other write operation. The payout dict exists only in memory for the duration of the caller's execution. If no caller persists it, the payout record is lost. The module header states "All writes go through booking_financial_facts and admin_audit_log" — this is not true for payout generation. The function was written without persistence, and there is no confirmed caller that writes the result.

# Exact repository evidence

- `src/services/financial_writer.py` lines 90–136 — `generate_payout_record` function
- `src/services/financial_writer.py` lines 30–87 — `record_manual_payment` (comparison: this one DOES persist)
- `src/services/financial_writer.py` line 9 — module header claim: "All writes go through booking_financial_facts and admin_audit_log"
- `src/api/financial_router.py` — the catch-all financial API (caller candidate)
- `src/api/financial_dashboard_router.py` — the dashboard financial API (caller candidate)
- `ihouse-ui/app/(app)/financial/statements/page.tsx` — owner statement UI

# Detailed evidence

**`generate_payout_record` — full function body:**
```python
def generate_payout_record(
    db: Any,
    tenant_id: str,
    property_id: str,
    period_start: str,
    period_end: str,
    mgmt_fee_pct: float = 15.0,
) -> Dict[str, Any]:
    """
    Generate a payout record for an owner.
    Calculates total revenue, deducts management fee,
    and creates a payout entry.
    """
    try:
        facts_result = (
            db.table("booking_financial_facts")
            .select("booking_id, total_gross, net_to_property, management_fee")
            .eq("property_id", property_id)
            .gte("extracted_at", period_start)
            .lt("extracted_at", period_end)
            .execute()
        )
        facts = facts_result.data or []
    except Exception as exc:
        return {"error": str(exc)}

    total_gross = sum(float(f.get("total_gross", 0) or 0) for f in facts)
    mgmt_fee = round(total_gross * mgmt_fee_pct / 100, 2)
    net_payout = round(total_gross - mgmt_fee, 2)

    payout = {
        "payout_id": f"payout_{uuid.uuid4().hex[:8]}",
        "tenant_id": tenant_id,
        "property_id": property_id,
        "period_start": period_start,
        "period_end": period_end,
        "total_gross": round(total_gross, 2),
        "management_fee": mgmt_fee,
        "management_fee_pct": mgmt_fee_pct,
        "net_payout": net_payout,
        "bookings_count": len(facts),
        "status": "pending",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return payout  # ← no write call anywhere in this function
```

The function is 37 lines. Lines 104–115 are a DB read. Lines 117–134 are calculations. Line 136 is `return payout`. There is no write operation — no `db.table(...).insert(...)`, no `db.table(...).upsert(...)`, no `write_audit_event()` call, no sub-function that writes. The `payout_id` is generated with `uuid.uuid4()` — creating a unique identifier for a record that is never stored.

**Contrast with `record_manual_payment` — which DOES persist:**
```python
def record_manual_payment(db, tenant_id, booking_id, amount, ...):
    ...
    result = db.table("booking_financial_facts").upsert(
        {...},
        on_conflict="booking_id,tenant_id",
    ).execute()
    # AND writes to admin_audit_log
    db.table("admin_audit_log").insert({...}).execute()
    return {"payment_id": ..., "status": "recorded"}
```
`record_manual_payment` writes to two tables. It also logs to the audit trail. The asymmetry between these two functions in the same file is stark. The module header's claim — "All writes go through booking_financial_facts and admin_audit_log" — is accurate for `record_manual_payment` and misleading for `generate_payout_record`, which does not write at all.

**Module header claim vs reality:**
```
All writes go through booking_financial_facts and admin_audit_log.
```
This statement is false for payout generation. The discrepancy suggests either: (a) the docstring was written before the decision was made to not persist payouts, or (b) the intent was always that the caller would persist the returned dict, and the docstring describes the intended downstream write that was never implemented.

**The `status: "pending"` field:**
The payout dict includes `"status": "pending"`. This implies a lifecycle — pending → approved → paid. But there is no status transition mechanism if no payout table exists. The "pending" status is decorative in the current implementation.

**The `payout_id` is generated but unreachable:**
`payout_id` is generated as `payout_{uuid.uuid4().hex[:8]}` on every call. If the same property/period is queried twice, two different `payout_id` values are generated. Neither is persisted. An owner who queries their payout twice will receive two different payout IDs for the same calculation, with no history retained.

**What callers are expected to do — unknown:**
The function is defined in a service module. It can be called from any router. The question of whether any router calls it and persists the result was not confirmed during reading. `financial_router.py` and `financial_dashboard_router.py` are candidates. Neither was read at the level of detail needed to confirm this. This is the most critical unknown.

**The owner statement UI:**
`ihouse-ui/app/(app)/financial/statements/page.tsx` is the owner statement frontend. If it calls an endpoint that calls `generate_payout_record` and displays the ephemeral result (without the endpoint persisting it), the UI can display correct payout calculations to owners without those calculations ever being written anywhere. The owner sees a number. The system has no record that it was shown.

# Contradictions

- The function docstring says "creates a payout entry." The function does not create an entry — it creates a dict. "Entry" implies database persistence. This is misleading.
- The module header says "All writes go through booking_financial_facts and admin_audit_log." Payout generation is not a write at all.
- `status: "pending"` implies a status machine. There is no table for payout status and no status transition logic.
- `payout_id` with UUID implies unique identity and retrievability. Neither is possible without persistence.

# What is confirmed

- `generate_payout_record` contains no database write operations.
- The function reads from `booking_financial_facts`, calculates correctly, and returns a dict.
- The returned dict includes a generated UUID-based `payout_id` that is ephemeral.
- The returned dict includes `status: "pending"` with no corresponding persistence model.
- `record_manual_payment` in the same file DOES persist to the database — confirming the omission in `generate_payout_record` is real, not a pattern decision.

# What is not confirmed

- Whether any caller of `generate_payout_record` persists the returned dict to a table. The callers in `financial_router.py` or `financial_dashboard_router.py` were not fully read at this level of detail.
- Whether a `payouts` or `owner_payouts` table exists in any migration file. If such a table exists, it may be intended as the persistence target for this function's output.
- Whether the owner statement frontend (`/financial/statements`) displays payout data from a table or from an ephemeral API call. If the data is ephemeral, owners cannot retrieve historical payout statements.
- Whether any payout data is exposed to owners in the owner portal v2 financial summary (which reads from `booking_financial_facts` directly — not from a payouts table).

# Practical interpretation

If `generate_payout_record` is called by a router that returns its output to the frontend but does not persist it, the system can calculate and display accurate owner payout statements — but cannot retain a history of payouts issued, approved, or paid. An owner portal might show "you are owed 45,000 THB for March" today, and that same query tomorrow might show a different number if bookings changed, with no record of what was shown before.

For an operational property management system, this is a critical gap in the financial lifecycle. A management company needs to be able to:
- Generate a payout for a period
- Record that it was reviewed and approved
- Mark it as paid with a payment reference
- Retain the history for reconciliation

None of these steps are possible if the payout dict is never written to a table.

This is not a bug in the calculation — the math appears correct. It is a missing persistence step at the boundary between calculation and commitment.

# Risk if misunderstood

**If assumed fully working:** The system is believed to track payout history. In practice, no payout history exists. Financial reconciliation is impossible. Owner disputes about past payments cannot be resolved from system records.

**If assumed purely calculation-only by design:** The owner statement UI may be presented to owners as showing their "statement" — implying a record — when it is showing a live calculation. The epistemic tier system (`A/B/C` for measured/calculated/incomplete) that exists in the financial dashboard would classify this as at most tier B (calculated) with no tier A (measured/committed) payout records.

**If someone adds a payouts table without understanding the existing function:** They may call `generate_payout_record` and write the result, not realizing the function generates a new UUID on every call. Deduplication logic must be added to avoid inserting multiple payout records for the same period on repeated calls.

# Recommended follow-up check

1. Read `src/api/financial_router.py` fully to find any caller of `generate_payout_record` and determine whether the caller persists the returned dict.
2. Search for a `payouts` or `owner_payouts` table in all migration files — if such a table exists, find the expected write path.
3. Read `ihouse-ui/app/(app)/financial/statements/page.tsx` fully to determine what API endpoint it calls and whether the payout data shown is from a table or an ephemeral calculation.
4. Search `src/` for all references to `generate_payout_record` to find every caller in the codebase.
