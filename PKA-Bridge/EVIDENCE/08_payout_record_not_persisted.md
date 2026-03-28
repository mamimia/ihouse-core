# Claim

`generate_payout_record` in `src/services/financial_writer.py` calculates an owner payout and returns a dict with a generated `payout_id` and `status: "pending"` — but contains no database write operation.

# Verdict

PROVEN

# Why this verdict

Direct reading of `src/services/financial_writer.py` lines 90–136 shows the function reads from `booking_financial_facts`, performs arithmetic, constructs a dict, and returns it. There is no `db.table(...).insert(...)`, no `db.table(...).upsert(...)`, no write of any kind. The same file contains `record_manual_payment` which DOES write to two tables — confirming the absence in `generate_payout_record` is a real omission, not a module-wide pattern. The caller of this function (`financial_writer_router.py`) was confirmed separately (Investigation 14): it calls the function and returns the result via HTTP response with no intermediate write.

# Direct repository evidence

- `src/services/financial_writer.py` lines 90–136 — `generate_payout_record` full function body
- `src/services/financial_writer.py` lines 30–87 — `record_manual_payment` (contrast: this one persists)
- `src/services/financial_writer.py` line 9 — module header: "All writes go through booking_financial_facts and admin_audit_log" (inaccurate for payout generation)
- `src/api/financial_writer_router.py` lines 99–122 — the only caller (confirmed by codebase grep)

# Evidence details

**`generate_payout_record` — no write in the function body:**
```python
def generate_payout_record(db, tenant_id, property_id, period_start, period_end, mgmt_fee_pct=15.0):
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
        "payout_id": f"payout_{uuid.uuid4().hex[:8]}",  # new UUID every call
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

    return payout  # ← no write anywhere in this function
```

**`record_manual_payment` in the same file — for contrast:**
```python
result = db.table("booking_financial_facts").upsert({...}, on_conflict="booking_id,tenant_id").execute()
db.table("admin_audit_log").insert({...}).execute()
```
Two writes. Confirms the missing writes in `generate_payout_record` are an actual absence, not a module convention.

# Conflicts or contradictions

- Function docstring: "creates a payout entry" — no entry is created.
- Module header: "All writes go through booking_financial_facts and admin_audit_log" — payout generation writes to neither.
- `status: "pending"` and a UUID `payout_id` imply a persistent, retrievable record. Neither is true.

# What is still missing

- Whether a `payouts` table exists in any migration not yet searched.
- Whether the frontend stores the returned dict locally as a workaround.

# Risk if misunderstood

Operators who generate payouts believe they have a committed record. No record exists. Payout history is impossible to query or audit from this system.
