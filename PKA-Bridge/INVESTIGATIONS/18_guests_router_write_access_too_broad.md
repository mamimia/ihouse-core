# Title

guests_router Has No Role Guard — Any Authenticated Tenant User Can Create, Read, and Edit Guest Records Including Passport PII With No Audit Trail

# Why this matters

The `guests` table is the system's canonical repository for guest identity records. It contains passport numbers, nationalities, dates of birth, document types, document photo URLs, and document expiry dates. These are among the most sensitive PII fields the system handles. `guests_router.py` (Phase 192) protects these records only with JWT validity and tenant isolation — no role check, no capability guard, no write audit log. A cleaner, checkout worker, or maintenance worker with a valid JWT can enumerate all guest records for the tenant, create synthetic guest entries, or overwrite passport numbers and document photos. The system logs none of this. The risk is particularly acute because the backend URL is visible in the browser network tab during normal worker-facing frontend usage, meaning the endpoint path is not obscure.

# Original claim

`POST /guests`, `GET /guests`, `GET /guests/{id}`, and `PATCH /guests/{id}` are protected only by `Depends(jwt_auth)`. Role is never checked. Any authenticated user in the tenant can create and edit sensitive guest PII fields.

# Final verdict

PROVEN

# Executive summary

Direct reading of `src/api/guests_router.py` (355 lines, Phase 192) confirms that all four endpoints use only `tenant_id: str = Depends(jwt_auth)` with no second dependency. The module header explicitly states "JWT auth required on all endpoints" with no role restriction mentioned. `require_capability` is not imported. The router uses `SUPABASE_SERVICE_ROLE_KEY`, bypassing RLS entirely. The `_PATCHABLE_FIELDS` frozenset includes `passport_no`, `date_of_birth`, `document_photo_url`, `document_type`, `passport_expiry`, and `nationality` — all sensitive document-level PII. No `write_audit_event()` call exists anywhere in the file. The exposure is confirmed, real, and unlogged.

# Exact repository evidence

- `src/api/guests_router.py` lines 75–78 — `POST /guests`: `Depends(jwt_auth)` only, no capability guard
- `src/api/guests_router.py` lines 132–135 — `GET /guests`: `Depends(jwt_auth)` only
- `src/api/guests_router.py` lines 200–203 — `GET /guests/{id}`: `Depends(jwt_auth)` only
- `src/api/guests_router.py` lines 258–261 — `PATCH /guests/{id}`: `Depends(jwt_auth)` only
- `src/api/guests_router.py` lines 239–242 — `_PATCHABLE_FIELDS` includes PII fields
- `src/api/guests_router.py` line 54 — `SUPABASE_SERVICE_ROLE_KEY` — RLS bypassed
- `src/api/guests_router.py` lines 12–13 — module rules: JWT + tenant isolation only
- `src/api/capability_guard.py` lines 100–113 — guard logic for contrast (requires explicit import + Depends)

# Detailed evidence

**The guest record schema — what is exposed:**
The `guests` table contains, and the PATCH endpoint can modify:
```python
_PATCHABLE_FIELDS = frozenset({
    "full_name", "email", "phone", "nationality", "passport_no", "notes",
    "document_type", "passport_expiry", "date_of_birth", "document_photo_url"
})
```
`passport_no`, `date_of_birth`, `document_photo_url`, `nationality`, `document_type`, `passport_expiry` are all document-level PII. A cleaner patching `passport_no` to a fraudulent value has no server-side barrier.

**All four endpoints — identical auth pattern:**
Every endpoint in the file uses exactly `tenant_id: str = Depends(jwt_auth)` as its only FastAPI dependency beyond the path/query parameters. No `require_capability`, no `jwt_identity`, no role extraction. The auth module import (`from api.auth import jwt_auth`) has only `jwt_auth` — `require_capability` is not imported at all.

**What `jwt_auth` provides:**
From Investigation 06: `jwt_auth` validates JWT signature/expiry, extracts `sub` claim as `tenant_id`, returns it. Does NOT check the `role` claim. A cleaner JWT and an admin JWT are indistinguishable to `jwt_auth`.

**RLS bypass via service role key:**
```python
def _get_supabase_client() -> Any:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)
```
The Supabase client is initialized with the service role key, which bypasses all RLS policies. Even if a future migration added RLS to the `guests` table, this router would not be subject to it. The FastAPI layer is the only enforcement point — and it has no role check.

**No write audit trail:**
A scan of `guests_router.py` finds no call to `write_audit_event()`, no call to any audit logger, no write to `admin_audit_log`. Contrast with `record_manual_payment` in `financial_writer.py` (Issue 13), which explicitly writes to `admin_audit_log`. Guest record creation and modification produce no audit trail. There is no way to determine who created or modified a guest record after the fact, beyond checking the Supabase service's own logs.

**The attack surface is not obscure:**
The backend URL is transmitted in the browser's network tab during normal frontend usage. A worker using `/ops/checkin` sees the network calls to the backend domain. With a valid session JWT (stored in sessionStorage or cookie depending on session type), that worker can call `POST /guests` or `PATCH /guests/{id}` directly. No special technical knowledge is required beyond being able to read a browser network tab.

**Comparison with the worker-facing identity write path:**
`checkin_identity_router.py` (Phase 949d) also writes guest identity data via `POST /worker/checkin/save-guest-identity`. That endpoint is on the `/worker/` prefix. The middleware restricts `/worker` to roles: `worker`, `cleaner`, `ops`, `checkin`, `checkout`, `maintenance`. So the worker-path identity write is accessible to those roles — but it is specifically scoped to check-in identity capture, not free-form guest record editing.

`guests_router.py` at the `/guests/` prefix is accessible to any role whose middleware allows `/guests`. From `ROLE_ALLOWED_PREFIXES`, only `ops` has `/guests` in its list. Worker, cleaner, and other field roles do NOT have `/guests` in their allowed prefixes at the middleware layer.

**Critical implication — the middleware adds a partial front-line defense:**
- `/guests` is in the `ops` allowlist only
- `worker`, `cleaner`, `checkin`, `checkout`, `maintenance` do NOT have `/guests` in their middleware allowlist
- BUT: middleware only governs Next.js routes, not direct API calls
- A worker making a direct HTTP call to `https://[backend]/guests` bypasses middleware entirely
- The worker's JWT passes `jwt_auth` (role-blind) and the call succeeds

This means:
1. Workers using the frontend cannot navigate to a `/guests` page (middleware blocks it)
2. Workers making direct API calls can reach all `/guests` endpoints (no role check at the API layer)

The protection exists at the UI layer but not at the API layer. This is the same structure that made the staff performance exposure real (Issue 06).

**Which roles can reach /guests from the frontend:**
Only `ops` (per `ROLE_ALLOWED_PREFIXES`). Admins and managers have full access. Workers, cleaners, and other field roles cannot navigate to `/guests` pages — but can call the API directly.

# Contradictions

- Module header says "Tenant isolation: reads and writes are always filtered by tenant_id" — implying isolation is sufficient. But isolation within a tenant means nothing for the multi-role concern: a tenant may have cleaners and admins who should have very different access to PII.
- The `guests` table is described as "first-class identity record managed by operators" — "operators" implies management-level access, not all authenticated users. But the code does not enforce this.
- `write_audit_event()` is used in checkin identity writes (`checkin_identity_router.py`) and in manual payment writes (`financial_writer.py`). The guests router — which handles the same or more sensitive identity data — has no audit logging. This is an inconsistency in the codebase's audit coverage.
- RLS bypass via service role key exists in this router, the same pattern identified in staff_performance_router and financial_writer_router as an amplifying risk factor.

# What is confirmed

- All four `guests_router.py` endpoints use only `Depends(jwt_auth)` — no role check, no capability guard
- `_PATCHABLE_FIELDS` includes `passport_no`, `date_of_birth`, `document_photo_url` and other document PII
- Service role key bypasses RLS — FastAPI layer is sole enforcement
- No audit log write exists in the router
- `jwt_auth` is role-blind — confirmed by Issue 06 investigation
- The middleware restricts `/guests` frontend navigation to `ops` only — but this does not protect the API from direct HTTP calls

# What is not confirmed

- Whether any currently deployed worker or cleaner has ever called `/guests` or `/guests/{id}` directly
- Whether the Phase 192 design intent was to allow all authenticated users or specifically operators — the module header is ambiguous
- Whether the `guests` table has RLS policies in migrations (would be bypassed anyway by service role key, but relevant for any future read path that uses a user-scoped key)
- Whether the checkin identity save path (`/worker/checkin/save-guest-identity`) creates guest records in the same `guests` table — if it does, those records then become editable by anyone via `PATCH /guests/{id}` with no role check

# Practical interpretation

**For a worker or cleaner in the current system:**
- Cannot navigate to `/guests` in the frontend (middleware blocks it)
- CAN call `GET /guests` via direct HTTP call — receives all guest records for the tenant (up to 200, with `passport_no`, `date_of_birth`, `document_photo_url` exposed)
- CAN call `POST /guests` — creates a synthetic guest record with any PII values
- CAN call `PATCH /guests/{id}` — overwrites any PII field on any guest record in the tenant
- None of this leaves an audit trail

**For an ops user in the current system:**
- Can navigate to `/guests` in the frontend (middleware allows it)
- Can create and edit guest records
- This is likely intentional — ops is the Operational Manager, guest coordination is in scope

**The threshold question:**
Is the open-to-all-authenticated-users state for the API (beyond what the frontend allows) intentional or an oversight? The module header's "operators" language and the absence of any role comment suggest it may have been written assuming only managers/admins would call it, without verifying the enforcement at the API layer.

# Risk if misunderstood

**If "only ops can navigate to /guests" is assumed to mean only ops can call the guests API:** Direct API callers bypass middleware entirely. The frontend restriction is UI-only.

**If the module's "tenant isolation" is assumed to be sufficient:** Tenant isolation prevents cross-tenant access. It does not prevent a low-privilege worker within the same tenant from reading full guest PII or overwriting passport data.

**If the absence of explicit complaints means no one has abused this:** The backend URL is visible in browser network tabs. There is no audit log. There is no way to detect past abuse.

# Recommended follow-up check

1. **Determine design intent for `/guests` write access:** Should `POST /guests` and `PATCH /guests/{id}` be restricted to admin/manager/ops only, or should all authenticated tenant users be allowed to create/edit guest records?

2. **If restriction is warranted:** Add `Depends(require_capability("guests"))` to `POST /guests` and `PATCH /guests/{id}` — or use a simpler role check for `admin`/`manager`/`ops` only. The `GET` endpoints are lower risk but should also be assessed.

3. **Add audit logging regardless of access decision:** `POST /guests` and `PATCH /guests/{id}` modify PII records. A `write_audit_event()` call with `entity_type="guest"`, `entity_id=guest_id`, `action="created"/"patched"`, and `actor_id` from the JWT would provide the audit trail that currently does not exist.

4. **Verify whether `save-guest-identity` writes to the same `guests` table:** If check-in identity capture creates records in `guests`, those records are then freely patchable via the unguarded `PATCH /guests/{id}` endpoint — including by the same worker who just captured the identity during check-in.
