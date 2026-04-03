# Title

Payout Endpoint Caller Confirmed No Persistence — Investigation Correct; Classified as Deferred Feature; Cosmetic Corrections Applied

# Related files

- Investigation: `INVESTIGATIONS/14_payout_endpoint_caller_confirmed_no_persist.md`
- Evidence: `EVIDENCE/14_payout_endpoint_caller_confirmed_no_persist.md`
- Companion: `VERIFICATIONS/08_payout_record_not_persisted.md` — same feature gap, different angle (Issue 08 covered the service function; Issue 14 confirmed the caller chain)

# Original claim

`financial_writer_router.py` is the only caller of `generate_payout_record()`. The router calls the function, receives the payout dict, and returns it directly via HTTP response with no intermediate write. The `payout_id` UUID and `status: "pending"` field are ephemeral — unretrievable after the HTTP response closes.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict: Investigation fully correct. Classified as intentionally deferred incomplete feature. No urgent fix warranted.**

**All 5 questions answered:**

**1. Confirmed caller of `generate_payout_record()`?**
One definition, one caller — confirmed by both grep and direct code read. The capability guard applied in Issue 13 (`require_capability("financial")`) now gates this caller. Nothing else calls `generate_payout_record()` anywhere in the codebase.

**2. Returns payout dict without persistence?**
Confirmed at every layer:
- DB query: zero payout-related tables exist in Supabase
- Frontend: zero references to `payout_id` — the result is displayed and forgotten
- The HTTP response evaporates completely after the request closes

**3. Payout history doesn't exist anywhere?**
Correct. No table, no migration, no frontend persistence, no query endpoint. The system has never had payout history.

**4. Deferred feature or active production bug?**
Deferred feature. The distinction:
- No existing data is being corrupted or silently lost — the system never promised persistence
- Operators have a workaround (manual records, export to accounting software)
- Building it correctly requires product decisions (approval workflow, who can approve, mark-paid flow, dispute handling) — cannot be implemented as a pure backend task

**5. Immediate action needed?**
Two cosmetic corrections only — applied now:

| Change | Why |
|--------|-----|
| `status: "pending"` → `status: "calculated"` | `"pending"` implies a lifecycle state machine that doesn't exist. `"calculated"` accurately describes what the function produces. |
| Docstrings and module header corrected | Previous: "creates a payout entry", "Generate owner payout records" — now explicitly state calculation-only, not persisted, deferred feature |
| OpenAPI endpoint summary corrected | Now reads: "Calculate owner payout (calculation only, not persisted)" |

**Formal backlog item documented:**
When the payout lifecycle is eventually built, it will require:
1. `payouts` table: `payout_id`, `property_id`, `tenant_id`, `period`, amounts, `status`, `approved_by`, `paid_at`
2. `POST /admin/financial/payout` → upsert into `payouts` instead of returning ephemeral dict
3. `GET /admin/financial/payouts?property_id=&period=` → query history
4. `PATCH /admin/financial/payouts/{id}` → status transitions (`pending → approved → paid`)
5. Frontend payout history panel

None of this should be built until the product workflow is defined.

# Verification reading

No additional repository verification read performed. The implementation response confirms all five questions and introduces the status string correction — a meaningful semantic fix that prevents the `"pending"` value from implying an unbuilt state machine.

# Verification verdict

RESOLVED

The investigation's facts are fully confirmed. The finding is correctly classified as an intentionally deferred incomplete feature. The cosmetic corrections make the current deferred state honest and prevent future misreading of the `status` field.

# What changed

`src/services/financial_writer.py`:
- `status: "pending"` in the returned payout dict changed to `status: "calculated"`
- `generate_payout_record()` docstring corrected to state: calculation-only, not persisted, deferred feature
- Module header corrected to remove claims that imply persistence

`src/api/financial_writer_router.py`:
- OpenAPI endpoint summary for `POST /admin/financial/payout` corrected to: "Calculate owner payout (calculation only, not persisted)"

Additionally (from Verification 13): `require_capability("financial")` was already added to the `POST /admin/financial/payout` endpoint in the Issue 13 fix. The single caller is now capability-gated.

# What now appears true

- `generate_payout_record()` is correctly characterized in code as a pure calculation function. The `status: "calculated"` field no longer implies a lifecycle.
- The payout workflow is incomplete by design. No table has ever existed for payout records.
- The capability guard (added in Issue 13) now gates the only caller. Even as a calculation-only endpoint, it is restricted to admin and capability-delegated managers.
- The payout ID (`payout_{uuid.uuid4().hex[:8]}`) is still generated on every call and still ephemeral. This could be removed entirely since there is no lifecycle to track, but was not changed — the ID may be useful as a response correlation handle even without persistence.
- The production owner financial flow (`owner_statement_router.py`) is unaffected — it reads directly from `booking_financial_facts` and has never used `generate_payout_record()`.

# What is still unclear

- **Whether any operators have been using `POST /admin/financial/payout` via direct API call** and treating the response as a real record. If so, those operators have been generating payout calculations with no persistence — their "payout history" exists only in whatever they noted down from the response. This cannot be detected from code alone.
- **Whether `status: "calculated"` is the final intended status string** for the deferred state, or whether it should eventually become `"draft"` once the full state machine (`draft → approved → paid`) is built. Not a blocking question — `"calculated"` is accurate for the current deferred state.

# Recommended next step

**Close both Issue 08 and Issue 14 against the same root finding.** The two investigations approached the same gap from different angles (service function vs. caller chain). Both are now confirmed, classified, and the code is honest about the deferred state.

**The payout lifecycle as a future build:**
The backlog item is well-defined. The prerequisites before building:
1. Product decision on the approval workflow: who approves payouts? (admin only? manager with financial capability?)
2. Product decision on the mark-paid flow: does `paid_at` record a Supabase transaction, or just a timestamp?
3. Schema design for `payouts` table must account for idempotency on (tenant_id, property_id, period_start, period_end) to prevent duplicate records from multiple calls for the same period
4. The existing `require_capability("financial")` guard on the endpoint means the authorization model is already in place — it just needs the persistence layer underneath it
