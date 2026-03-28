# Title

Payout Record Not Persisted — Investigation Factually Correct; Severity Lower Than Implied; Function Is Orphaned Phase 502 Incomplete Feature

# Related files

- Investigation: `INVESTIGATIONS/08_payout_record_not_persisted.md`
- Evidence: `EVIDENCE/08_payout_record_not_persisted.md`

# Original claim

`generate_payout_record()` calculates an owner payout and returns a dict with a generated `payout_id` and `status: "pending"` but contains no database write operation. Operators who generate payouts believe they have a committed record. No record exists.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict from implementation layer: Investigation is correct that the function doesn't persist, but the practical severity is lower than implied.**

`generate_payout_record()` is an orphaned Phase 502 calculation helper with no frontend consumer. The production owner statement flow is a separate, complete pipeline (`owner_statement_router.py`) that reads `booking_financial_facts` directly and never calls this function. No owner-facing financial data is at risk.

**All 5 questions answered:**

**1. Does `generate_payout_record` only calculate and return a dict?**
Confirmed. Lines 90–136 of `financial_writer.py`:
- Lines 104–113: reads from `booking_financial_facts`
- Lines 117–119: arithmetic (sum gross, compute fee, compute net)
- Lines 121–134: constructs dict with `payout_id`, `status: "pending"`, etc.
- Line 136: `return payout` — no write operation anywhere

The contrast with `record_manual_payment` (lines 30–87) in the same file — which writes to two tables — confirms this is a real omission.

**2. Does any caller persist the payout record?**
No. One caller exists in the codebase:
```python
# financial_writer_router.py lines 99–122
async def generate_payout_endpoint(...):
    result = generate_payout_record(db=db, ...)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return JSONResponse(status_code=200, content=result)  # ← no persistence
```
The dict is returned as HTTP response and garbage collected. No intermediate write.

**3. Do `payout_id` and `status="pending"` represent a real lifecycle?**
No — they are decorative:
- `payout_id`: Generates a new `payout_{uuid.uuid4().hex[:8]}` on every call. Calling the same endpoint twice produces two different IDs. Neither is stored. The ID is unretrievable after the HTTP response closes.
- `status: "pending"`: Hardcoded string. No transition mechanism, no persistence target, no workflow to `"approved"` or `"paid"`. It implies a lifecycle that does not exist.

**4. Does the owner statement / payout flow show uncommitted financial output?**
No. The production owner financial flow is entirely separate:

| Flow | Frontend page | Backend endpoint | Uses `generate_payout_record`? |
|------|-------------|-----------------|-------------------------------|
| Owner statement (production) | `/financial/statements` | `GET /owner-statement/{property_id}` | ❌ No — reads `booking_financial_facts` directly |
| Owner portal financial view | `/owner` | `GET /financial/aggregated` | ❌ No — uses `financial_aggregation_router` |
| Payout generation (orphaned) | _(none)_ | `POST /admin/financial/payout` | ✅ Yes — but no frontend calls this |

`owner_statement_router.py` (464 lines, Phase 121) is a complete, independent pipeline:
- Reads `booking_financial_facts` directly
- Builds per-booking line items with epistemic tiers
- Computes management fee deductions
- Generates PDF export via `generate_owner_statement_pdf()`
- Has proper role scoping (owner `property_id` verification)

No owner sees `payout_id` or the ephemeral dict. The investigation's concern about operators believing they have a committed record applies only to whoever directly calls `POST /admin/financial/payout` via API — and there is currently no frontend surface that does so.

**5. Is there an existing persistence target or payout table?**
None. Full search confirmed:
- All `.py` files in `src/` for `payouts`, `owner_payouts`, `payout_records` → no table reference
- All `.sql` migration files for `CREATE TABLE.*payout` → no migration
- Supabase schema → no payouts table

The `generate_payout_record` function was built (Phase 502) as the first half of a payout workflow — calculate — without the second half: persist → approve → pay. The table was never created.

**Diagnosis:**
An incomplete Phase 502 deliverable. The function works correctly as a calculator. The lifecycle it implies (`payout_id`, `status: "pending"`, unstated transitions to "approved"/"paid") was never built.

**Why this is not operationally dangerous right now:**
- No frontend consumer exists. `POST /admin/financial/payout` has no button, form, or page that calls it. Reachable via direct API call only.
- The real financial flow is separate and complete. `GET /owner-statement/{property_id}` provides full per-booking statements with epistemic tiers, management fees, and PDF export.
- No owner sees payout IDs. The owner portal uses `GET /financial/aggregated` (reads `booking_financial_facts` directly).

**Deferred build path (when ready):**
1. Create `owner_payouts` table (payout_id, tenant_id, property_id, period_start, period_end, total_gross, management_fee, net_payout, status enum, generated_at, approved_at, paid_at, payment_reference)
2. Add persistence to the function — insert into `owner_payouts` with idempotency (upsert on `tenant_id + property_id + period_start + period_end`)
3. Add status transition endpoints — `PATCH /admin/financial/payout/{payout_id}/approve` and `/mark-paid`
4. Wire to frontend — add payout management surface in admin financial dashboard

**Changes made: None.** Treated as incomplete feature, not a bug.

# Verification reading

No additional repository verification read was performed. The implementation response confirms every point in the investigation with specific line references and adds critical new context: the production financial flow (`owner_statement_router.py`) is completely independent of `generate_payout_record`. This context was missing from the investigation and materially changes the severity assessment.

# Verification verdict

PARTIALLY RESOLVED

The investigation's factual findings are confirmed entirely correct. The severity framing is revised: the missing persistence is an incomplete deferred feature rather than an operational risk to current owner-facing financial data. No fix applied; no owner data at risk. The risk becomes real only when a frontend consumer of `POST /admin/financial/payout` is built — at that point, persistence must be added before the endpoint is exposed to users.

# What changed

Nothing. No code was modified.

# What now appears true

- `generate_payout_record()` is an orphaned Phase 502 calculation function with no frontend consumer, no persistence, and no lifecycle.
- `payout_id` is ephemeral and unretrievable. `status: "pending"` implies a lifecycle that was never built.
- The docstring claim "creates a payout entry" is still false — no entry is created.
- The production owner financial output path is `owner_statement_router.py` + `GET /owner-statement/{property_id}`, which is a complete, separate pipeline reading `booking_financial_facts` directly. It is unaffected by the payout function's missing persistence.
- No `owner_payouts` table exists anywhere in migrations or schema. If the payout lifecycle is ever built, the table must be created first.
- The operational risk the investigation described — "operators believe they have a committed record" — exists only for direct API callers. There is currently no frontend surface that calls this endpoint.

# What is still unclear

- **Whether `POST /admin/financial/payout` has been called in production** by any admin operating via API directly. If it has, those callers received ephemeral payout dicts they may have treated as records. This cannot be determined without checking `admin_audit_log` or HTTP access logs.
- **Whether the Phase 502 payout lifecycle was intentionally deferred** or was an accidental incompletion. The investigation cannot determine intent from reading alone.
- **Whether `financial_writer_router.py`'s missing role guard** (Issue 13) means `POST /admin/financial/payout` is reachable by any authenticated user, not just admins. Given the current orphaned state this is low severity, but it becomes a real risk when a frontend consumer is built.

# Recommended next step

**Close the operational risk finding.** The production financial output to owners is correct and unaffected. No owners are seeing uncommitted or ephemeral payout data.

**Treat as a product backlog item, not a bug fix:**
- The payout lifecycle (`owner_payouts` table, status transitions, frontend surface) is a coherent feature to build when the roadmap reaches it.
- When that feature is built: persistence and idempotency must be added to `generate_payout_record()` before any frontend surface calls `POST /admin/financial/payout`.
- The missing role guard on `financial_writer_router.py` (Issue 13) must also be resolved before the payout endpoint is made user-facing.
- Add a note to the Phase 502 function docstring or a `# TODO: Phase NNN` comment flagging that the persistence half of this function was deferred — preventing a future reader from assuming the calculation implies a committed record.
