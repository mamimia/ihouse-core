# Claim

`guests_router.py` (`POST /guests`, `GET /guests`, `GET /guests/{id}`, `PATCH /guests/{id}`) uses only `Depends(jwt_auth)` with no capability guard. Any authenticated user in the tenant — regardless of role — can create and edit guest records, including sensitive PII fields (`passport_no`, `date_of_birth`, `document_photo_url`, `nationality`).

# Verdict

PROVEN

# Why this verdict

Direct reading of `src/api/guests_router.py` (355 lines, Phase 192) confirms every endpoint signature uses only `tenant_id: str = Depends(jwt_auth)` with no second dependency. No `require_capability()` call exists anywhere in the file. The module header explicitly states "JWT auth required on all endpoints" with no mention of role restriction. The router uses `SUPABASE_SERVICE_ROLE_KEY` (line 54), bypassing RLS at the DB layer. The only access control is JWT validity and tenant scoping — role is never checked.

# Direct repository evidence

- `src/api/guests_router.py` line 37 — `from api.auth import jwt_auth` (only auth import; no `require_capability`)
- `src/api/guests_router.py` line 77 — `POST /guests`: `tenant_id: str = Depends(jwt_auth)` only
- `src/api/guests_router.py` line 135 — `GET /guests`: `tenant_id: str = Depends(jwt_auth)` only
- `src/api/guests_router.py` line 202 — `GET /guests/{id}`: `tenant_id: str = Depends(jwt_auth)` only
- `src/api/guests_router.py` line 261 — `PATCH /guests/{id}`: `tenant_id: str = Depends(jwt_auth)` only
- `src/api/guests_router.py` line 54 — `key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]` — RLS bypassed
- `src/api/guests_router.py` lines 12–13 — module rules: "JWT auth required on all endpoints" (no role requirement stated)
- `src/api/guests_router.py` lines 239–242 — `_PATCHABLE_FIELDS` includes PII: `passport_no`, `date_of_birth`, `document_photo_url`, `nationality`, `document_type`, `passport_expiry`

# Evidence details

**All four endpoints — auth dependency only:**
```python
# POST /guests (line 75–77)
async def create_guest(
    body: dict,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    client: Optional[Any] = None,

# GET /guests (line 132–135)
async def list_guests(
    search: Optional[str] = None,
    limit: Optional[int] = None,
    tenant_id: str = Depends(jwt_auth),   # ← only guard

# GET /guests/{id} (line 200–203)
async def get_guest(
    guest_id: str,
    tenant_id: str = Depends(jwt_auth),   # ← only guard

# PATCH /guests/{id} (line 258–261)
async def patch_guest(
    guest_id: str,
    body: dict,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
```

**PII fields exposed to patch:**
```python
_PATCHABLE_FIELDS = frozenset({
    "full_name", "email", "phone", "nationality", "passport_no", "notes",
    "document_type", "passport_expiry", "date_of_birth", "document_photo_url"
})
```
A cleaner with a valid JWT can patch a guest's `passport_no`, `date_of_birth`, and `document_photo_url`.

**Service role key — RLS bypassed:**
```python
def _get_supabase_client() -> Any:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]   # ← bypasses RLS
    return create_client(url, key)
```
Even if RLS policies existed on the `guests` table, they would not apply. The FastAPI layer is the only enforcement boundary.

**Module header states no role requirement:**
```
Rules:
  - JWT auth required on all endpoints. `sub` claim = tenant_id.
  - Tenant isolation: reads and writes are always filtered by tenant_id.
```
No role restriction is stated. Tenant isolation is the only constraint beyond JWT validity.

**What `jwt_auth` provides (confirmed from Issue 06 investigation):**
`jwt_auth` validates JWT signature and expiry, extracts `tenant_id` from the `sub` claim, and returns `tenant_id`. It does NOT read or validate the `role` claim. A JWT from any role (cleaner, worker, owner, ops, checkin, checkout, maintenance) passes `jwt_auth` equally.

# Conflicts or contradictions

- `checkin_identity_router.py` (Phase 949d) performs similar guest identity writes via `save-guest-identity` — that endpoint is on the `/worker/` prefix, restricted to worker roles by middleware. But `guests_router.py` is mounted at the root-level `/guests` path, accessible from the frontend by any role whose middleware prefix list includes `/guests`.
- The `ops` role includes `/guests` in its `ROLE_ALLOWED_PREFIXES` — this was confirmed in Investigation 17. So ops-level guest read/write is an intended use case.
- The question is whether worker/cleaner/owner roles should also be able to create and edit guest records through this endpoint — not whether ops should.
- `guests` table contains document-level PII (passport number, photo URL, date of birth). The guests router has no write audit logging — no `write_audit_event()` call anywhere in the file. A modified or fabricated guest record leaves no audit trail.

# What is still missing

- Whether the `guests` table has any RLS policies in the Supabase migrations that would apply when accessed with a user-level JWT (the router uses service role key, so RLS never applies here regardless)
- Which frontend pages call the guests write endpoints — specifically, whether `/ops/checkin/page.tsx` uses `POST /guests` directly or uses `POST /worker/checkin/save-guest-identity` (the worker-scoped identity endpoint)
- Whether any frontend page accessible to cleaner or worker roles calls `POST /guests` or `PATCH /guests/{id}`
- Whether the decision to leave this unguarded was deliberate (open PII management model for all hospitality staff) or an oversight from Phase 192

# Risk if misunderstood

**If `jwt_auth` is assumed to include a role check:** It does not. Any valid JWT holder — cleaner, checkout worker, maintenance worker — can call `POST /guests` or `PATCH /guests/{id}` and create or modify guest identity records including passport numbers and document photos.

**If tenant isolation is assumed to be sufficient protection:** Tenant isolation prevents cross-tenant access. It does not prevent a low-privilege worker within the same tenant from reading all guest records or modifying sensitive PII fields.

**If this is left unguarded:** A worker or cleaner who knows the backend URL (visible in browser network tab during normal ops usage) can enumerate all guest records, create synthetic guest entries, or modify existing passport numbers and document photos without leaving any trace in the audit log.
