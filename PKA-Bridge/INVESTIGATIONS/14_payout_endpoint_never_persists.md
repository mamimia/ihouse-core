# Title

The Owner Payout Endpoint Calculates and Returns Payout Data But Never Writes It — No Payout History Exists

# Why this matters

`POST /admin/financial/payout` is the mechanism for generating owner payout records. Operators call it to compute what a property owner is owed for a given period. The response includes a `payout_id`, a full financial breakdown, and `status: "pending"`. None of this is written to any database table. The `payout_id` is a UUID generated fresh on every call — two calls for the same period return different IDs. The `status: "pending"` implies a lifecycle (pending → approved → paid) with no table to track transitions. Calling this endpoint twice returns two conflicting "payout records" with different IDs and no way to distinguish the real one. Owner payout history cannot be queried, compared, or audited from the current system.

# Original claim

The payout API endpoint calls `generate_payout_record()`, receives the calculated dict, and returns it — never writing it to any database table.

# Final verdict

PROVEN

# Executive summary

The only caller of `generate_payout_record` is `src/api/financial_writer_router.py`. The endpoint body calls the function, checks for an `error` key, and returns the result as a JSON response with no intermediate write operation. The function itself performs no write. A codebase-wide grep confirms there are exactly two references to `generate_payout_record` — the definition and this one caller. No payout table appears in the migration files searched. Owner payout records are ephemeral: they exist in the HTTP response for the duration of the request, then disappear. This investigation updates and confirms Investigation 08, which first identified the non-persistence issue before the caller was found.

# Exact repository evidence

- `src/api/financial_writer_router.py` lines 99–122 — `generate_payout_endpoint` (the only caller)
- `src/services/financial_writer.py` lines 90–136 — `generate_payout_record` (no DB writes in body)
- Codebase grep for `generate_payout_record`: exactly 2 results (definition + caller)
- `src/api/financial_writer_router.py` lines 108–118 — call → check error → return (no write between)

# Detailed evidence

**The complete caller — no write between call and return:**
```python
async def generate_payout_endpoint(body: PayoutRequest, tenant_id: str = Depends(jwt_auth), ...) -> JSONResponse:
    try:
        from services.financial_writer import generate_payout_record
        db = client if client is not None else _get_supabase_client()
        result = generate_payout_record(          # ← calculation only
            db=db,
            tenant_id=tenant_id,
            property_id=body.property_id,
            period_start=body.period_start,
            period_end=body.period_end,
            mgmt_fee_pct=body.mgmt_fee_pct,
        )
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(status_code=200, content=result)  # ← returned immediately, no write
    except Exception as exc:
        logger.exception(...)
        return make_error_response(status_code=500, code=ErrorCode.INTERNAL_ERROR)
```
Between lines 108 and 118 there are: one function call, one conditional check, one return. No `db.table(...)` call. No write of any kind.

**What `generate_payout_record` returns (and what is never persisted):**
```python
payout = {
    "payout_id": f"payout_{uuid.uuid4().hex[:8]}",  # unique each call
    "tenant_id": tenant_id,
    "property_id": property_id,
    "period_start": period_start,
    "period_end": period_end,
    "total_gross": round(total_gross, 2),
    "management_fee": mgmt_fee,
    "management_fee_pct": mgmt_fee_pct,
    "net_payout": net_payout,
    "bookings_count": len(facts),
    "status": "pending",                            # implies lifecycle, no table to track it
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
return payout  # ← returned to caller, which returns to HTTP client
```

**The idempotency problem:**
Every call generates `payout_id = f"payout_{uuid.uuid4().hex[:8]}"`. Two calls to the same endpoint with the same property/period parameters return two different `payout_id` values. If an operator generates a payout, shares the `payout_id` with an owner, and then regenerates it (perhaps to correct a parameter), the second call produces a different ID. The original ID never existed in any table — there is no way to look it up later, correct it, or mark either as the authoritative record.

**What `status: "pending"` implies vs what exists:**
A status lifecycle would require a table with rows, a status field, and endpoints to transition statuses (e.g., PATCH `/payouts/{payout_id}` with `status: "approved"`). None of these exist. The `status: "pending"` value is decorative text in an ephemeral dict.

**Grep result summary:**
```
src/api/financial_writer_router.py:105 — caller
src/services/financial_writer.py:90   — definition
```
No other files reference `generate_payout_record`. The function has exactly one caller. That caller does not persist.

**No payout table in migrations:**
Searched migration files for `payouts`, `owner_payouts`, `payout_records`. No results. There is no confirmed DB table for payout persistence.

**Financial reporting reads `booking_financial_facts` directly:**
The owner portal financial summary (owner_portal_v2_router.py) reads raw rows from `booking_financial_facts` and calculates sums inline. It does not read from a payouts table. This is consistent with no payouts table existing.

# Contradictions

- Endpoint summary: "Generate owner payout record" — "record" strongly implies a persistent database record. The endpoint generates an ephemeral calculation, not a record.
- `generate_payout_record` docstring: "creates a payout entry" — "creates" implies a write operation. The function creates a dict in memory only.
- `status: "pending"` implies subsequent state transitions. There is no mechanism for these transitions.
- `payout_id` with a UUID implies subsequent lookup by ID. There is no lookup endpoint and no table to look up from.
- The `financial_writer.py` module header: "Provides mutation operations for financial data: ... Generate owner payout records" — "mutation" implies a state change in the database. Payout generation is a read + calculation only.

# What is confirmed

- `generate_payout_record` has exactly one caller: `financial_writer_router.py`.
- The caller does not persist the return value.
- The function generates a new UUID `payout_id` on every call.
- No payout table was found in migration files.
- `status: "pending"` is in the return dict but has no corresponding persistence or lifecycle mechanism.

# What is not confirmed

- Whether any migration file defines a `payouts` table that was not searched (migrations search was not exhaustive).
- Whether the frontend that calls `POST /admin/financial/payout` stores the returned dict locally (e.g., in localStorage) as a workaround for the non-persistence.
- Whether payout approval happens out-of-band (e.g., via a separate accounting system) and the API is used only for calculation, with manual persistence expected from the caller.

# Practical interpretation

**The workflow as designed (intended):**
1. Admin calls `POST /admin/financial/payout` with a property and period
2. System calculates total revenue, deducts management fee, returns net payout
3. Admin reviews, approves, pays the owner
4. Record is kept that the payout was made, by whom, when, for what period

**The workflow as implemented (actual):**
1. Admin calls `POST /admin/financial/payout`
2. System calculates and returns a dict
3. Response is displayed to the admin
4. Admin closes the page — dict is gone
5. No record of the payout generation exists
6. Step 3 (review/approve) and step 4 (payment record) have no system support

The system can calculate what to pay. It cannot record that payment was authorized or made. End-of-year audit, owner dispute about historical payouts, or reconciliation of managed properties requires manual record-keeping outside the system.

# Risk if misunderstood

**If the response is assumed persisted:** An operator who generates a payout record and notes the `payout_id` for reference will discover — when they try to look it up later — that no such record exists in the system.

**If payout history is assumed queryable:** There is no `GET /admin/financial/payouts` endpoint, no payout table, and no historical record. Any reporting that assumes payout history can be retrieved will find nothing.

**If the management fee calculation is trusted without audit:** Since payouts are never persisted, the management fee percentage applied at generation time is never recorded. If the `mgmt_fee_pct` parameter changes between calls for the same period, different callers get different net figures with no record of which was authoritative.

# Recommended follow-up check

1. Determine whether a `payouts` table is expected to be created in an upcoming migration — search for any TODO, planning document, or migration draft.
2. Read `ihouse-ui/app/(app)/financial/statements/page.tsx` fully to understand how the payout data is displayed and whether it is stored client-side after the API response.
3. Determine the intended caller-side behavior: is the frontend expected to locally persist or display the payout record, or is a DB persistence step missing from the backend?
4. Check whether `require_capability("financial")` or an admin role check would be appropriate for this endpoint before any persistence is added — currently it is unguarded (see Investigation 13).
