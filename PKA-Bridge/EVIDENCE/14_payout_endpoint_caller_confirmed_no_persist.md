# Claim

The payout API endpoint (`POST /admin/financial/payout`) calls `generate_payout_record()`, receives the calculated dict, and returns it directly — never writing it to any database table.

# Verdict

PROVEN

# Why this verdict

`src/api/financial_writer_router.py` is the confirmed caller of `generate_payout_record`. The endpoint at lines 99–122 calls the function, checks for an `"error"` key, and returns the result as a JSON response. There is no write call between the function call and the return. The payout dict — including its generated `payout_id` — is returned to the API caller and then discarded. A codebase-wide grep finds no other callers of `generate_payout_record`. The function is called exactly once, and that one caller does not persist the result.

# Direct repository evidence

- `src/api/financial_writer_router.py` lines 99–122 — `generate_payout_endpoint`
- `src/services/financial_writer.py` lines 90–136 — `generate_payout_record` (no write in function body)
- Codebase grep: `generate_payout_record` appears in exactly 2 files — definition and one caller

# Evidence details

**The caller — full endpoint body:**
```python
async def generate_payout_endpoint(body: PayoutRequest, tenant_id: str = Depends(jwt_auth), ...) -> JSONResponse:
    try:
        from services.financial_writer import generate_payout_record
        db = client if client is not None else _get_supabase_client()
        result = generate_payout_record(
            db=db,
            tenant_id=tenant_id,
            property_id=body.property_id,
            period_start=body.period_start,
            period_end=body.period_end,
            mgmt_fee_pct=body.mgmt_fee_pct,
        )
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return JSONResponse(status_code=200, content=result)  # ← returned, never persisted
    except Exception as exc:
        ...
```

Between `result = generate_payout_record(...)` and `return JSONResponse(... content=result)`, there is no write operation. No `db.table(...).insert(...)`. No call to any persistence function. The dict is returned as-is.

**Grep results for `generate_payout_record`:**
```
src/api/financial_writer_router.py:105 — caller
src/services/financial_writer.py:90   — definition
```
Exactly two references. One definition, one caller. The caller does not persist.

**Consequence:** Every call to `POST /admin/financial/payout` generates a UUID-based `payout_id` and returns a `status: "pending"` record. The UUID is different on every call. No payout history accumulates. No `payout_id` is retrievable after the HTTP response completes.

# Conflicts or contradictions

- Endpoint summary: "Generate owner payout record" — "record" implies persistence.
- `generate_payout_record` docstring: "creates a payout entry" — "entry" implies persistence.
- `status: "pending"` implies a lifecycle. There is no table to transition it through.

# What is still missing

- Whether a `payouts` table exists in any migration (not found in migration files searched).
- Whether any other part of the system reads a persisted payout — if no table exists, nothing can read it.

# Risk if misunderstood

If an operator generates a payout via the UI and treats the response as a committed record they can reference later, they will find no trace of it when they look. Payout history does not exist. Financial reconciliation based on the payout endpoint's output is impossible.
