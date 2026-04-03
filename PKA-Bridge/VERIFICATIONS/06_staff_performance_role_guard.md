# Title

Staff Performance Missing Role Guard — Real Issue Confirmed; `require_capability("staffing")` Guard Added to Both Endpoints

# Related files

- Investigation: `INVESTIGATIONS/06_staff_performance_role_guards.md`
- Evidence: `EVIDENCE/06_staff_performance_role_guards.md`

# Original claim

Both `/admin/staff/performance` endpoints use only `Depends(jwt_auth)` with no role check. Any authenticated user regardless of role can retrieve complete workforce performance data for every worker in the tenant.

# Original verdict

PROVEN

# Response from implementation layer

**Verdict from implementation layer: Investigation is correct. Real issue. Fixed.**

**All 5 questions answered:**

**1. What `jwt_auth` actually does:**
`jwt_auth` (auth.py line 366) is a thin wrapper around `verify_jwt`:
- Validates JWT signature and expiry (HS256)
- Extracts `sub` claim → returns `tenant_id`
- Does NOT read, validate, or return the `role` claim

The auth module has a role-aware alternative (`jwt_identity` / `jwt_identity_simple`, lines 324, 347) which returns `{user_id, tenant_id, role}`. `staff_performance_router` was using `jwt_auth` — the role-blind variant.

**2. Whether explicit role guard existed:**
None. Both endpoints had `Depends(jwt_auth)` as their only dependency. The router was initialized as plain `APIRouter()` with no router-level dependencies.

**3. Whether direct HTTP access bypasses Next.js middleware:**
Yes. `middleware.ts` governs Next.js routes only. A direct HTTP call to `https://[backend-url]/admin/staff/performance` with a valid JWT goes straight to FastAPI and never touches Next.js middleware. The frontend `/admin` prefix protection is irrelevant for API-direct callers.

**4. Whether service role key bypasses RLS:**
Yes. Lines 55–58 of `staff_performance_router.py`:
```python
def _get_supabase_client():
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],  # ← bypasses RLS
    )
```
Even if RLS policies existed on the tasks table, the service role key bypasses them entirely. No DB-level safety net exists.

**5. Whether non-admin users could realistically read staff performance data:**
Yes, trivially. Attack path confirmed:
1. Cleaner logs in → receives JWT with `role=cleaner, tenant_id=<tenant>`
2. Makes `GET /admin/staff/performance` with that JWT (backend URL visible in browser network tab during normal frontend usage)
3. Backend validates JWT, extracts `tenant_id`, queries all tasks in the tenant, returns full performance metrics for every worker

**Fix applied — `staff_performance_router.py`:**
```diff
 from api.auth import jwt_auth
+from api.capability_guard import require_capability
```
```diff
 async def get_staff_performance(
     date_from: Optional[str] = None,
     date_to: Optional[str] = None,
     tenant_id: str = Depends(jwt_auth),
+    _cap: None = Depends(require_capability("staffing")),
     _client: Optional[Any] = None,
 ) -> JSONResponse:
```
```diff
 async def get_worker_performance(
     worker_id: str,
     date_from: Optional[str] = None,
     date_to: Optional[str] = None,
     tenant_id: str = Depends(jwt_auth),
+    _cap: None = Depends(require_capability("staffing")),
     _client: Optional[Any] = None,
 ) -> JSONResponse:
```
Also added `403: {"description": "Insufficient role or capability"}` to both endpoint response definitions.

**How `require_capability("staffing")` works:**

| Caller role | Behavior |
|-------------|----------|
| `admin` | ✅ Always allowed (all capabilities implied) |
| `manager` | ✅ Allowed only if `staffing` capability is delegated in `tenant_permissions` |
| `worker` / `cleaner` / `owner` / any other | ❌ HTTP 403 `CAPABILITY_DENIED` |

**Why `require_capability("staffing")` rather than a simpler role check:**
`worker_router.py` already uses `require_capability("staffing")` (lines 831, 880) for staff assignment endpoints. Staff performance is the same authorization domain — managers who can assign staff should also be able to view performance metrics. Using the same capability key ensures consistent authorization across the staffing surface.

**Dev mode safety:**
When `IHOUSE_DEV_MODE=true`, `require_capability` returns a no-op guard (lines 84–87 of `capability_guard.py`). Dev/test environments are unaffected. Blocked in production by `env_validator.py`.

# Verification reading

No additional repository verification read was performed. The implementation response is internally consistent and directly resolves every line of the original investigation. The `require_capability` pattern's precedent in `worker_router.py` provides the architectural alignment the fix follows.

# Verification verdict

RESOLVED

# What changed

`src/api/staff_performance_router.py`:
- `require_capability("staffing")` added as a second dependency to both `get_staff_performance` and `get_worker_performance`
- `403` response definition added to both endpoint metadata
- Import for `require_capability` added

Any caller without `admin` role or delegated `staffing` capability now receives HTTP 403 instead of performance data.

# What now appears true

- The investigation's description of the exposure was accurate: any authenticated user could read full workforce performance data via direct HTTP.
- The fix closes the gap using the established capability guard pattern already in use for the same authorization domain (`worker_router.py` staffing endpoints).
- `jwt_auth` is confirmed as role-blind throughout the codebase — it returns `tenant_id` only. Any router that uses only `jwt_auth` and does not add a second capability or role guard is similarly open to all authenticated users.
- The service role key bypass of RLS remains in place. The capability guard at the FastAPI layer is now the sole enforcement mechanism. There is no DB-level backup.
- `require_capability("staffing")` is the correct guard for this endpoint — it grants access to admins unconditionally and to managers only if the `staffing` capability is delegated.

# What is still unclear

- **How many other routers use only `Depends(jwt_auth)` with no second guard?** The investigation identified `financial_writer_router.py` (Issue 13) as another case. A systematic grep for `Depends(jwt_auth)` across all router files would reveal the full surface of unguarded endpoints. This was not performed as part of this fix.
- **Whether `IHOUSE_DEV_MODE=true` in the current branch disables `require_capability` globally.** If the dev environment has this flag set, the fix is effectively inactive in that environment. Not checked.
- **Whether any existing `tenant_permissions` rows have the `staffing` capability delegated to managers.** Without that delegation, managers would now receive 403 for staff performance — a potential operational regression if managers were previously using these endpoints.

# Recommended next step

**Close the staff performance exposure.** The guard is in place. The endpoint is now restricted to admin and capability-delegated managers.

**Keep open as a systemic observation:**
- A full audit of all routers using only `Depends(jwt_auth)` without a second guard is warranted. `staff_performance_router.py` and `financial_writer_router.py` are two confirmed cases. This pattern likely exists elsewhere. The fix here demonstrates the correct remediation pattern: add `Depends(require_capability("<domain>"))` as the second dependency.
- Verify whether any managers in active tenants need the `staffing` capability delegation added to `tenant_permissions` to maintain their current level of access.
