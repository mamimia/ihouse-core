# Title

Staff Performance Endpoints Are Accessible to Any Authenticated User, Not Just Admins

# Why this matters

`GET /admin/staff/performance` exposes aggregated performance metrics for all workers in a tenant: task completion rates, SLA compliance percentages, average acknowledgment times, preferred notification channels, and kind breakdowns. `GET /admin/staff/performance/{worker_id}` exposes the same data for a specific worker. Both endpoints are path-prefixed `/admin/` and tagged `["admin"]` — signaling admin-only intent. But neither endpoint enforces this. Any user with a valid JWT — cleaner, check-in agent, worker, owner — can call these endpoints directly and retrieve internal operational performance data for all coworkers in the tenant. The frontend middleware prevents non-admin users from reaching `/admin/` pages in the UI, but this does not protect the API endpoint itself, which is callable via direct HTTP with any valid token.

# Original claim

`staff_performance_router` lacks adequate role guards and is exposed more broadly than intended.

# Final verdict

PROVEN

# Executive summary

Both endpoints in `src/api/staff_performance_router.py` use `Depends(jwt_auth)` as their only authorization guard. `jwt_auth` validates JWT existence and returns `tenant_id` from the `sub` claim — it does not read or check the `role` claim. Neither endpoint body contains a role validation step. The router is initialized without router-level dependencies. The path prefix `/admin/staff/performance` and OpenAPI tag `"admin"` are documentation-only signals with no enforcement power. The result is that any valid JWT holder in the tenant can call these endpoints directly via HTTP and receive complete staff performance data. The frontend middleware (`middleware.ts`) blocks non-admin users from the `/admin/` UI routes, but direct HTTP calls to the FastAPI backend bypass middleware entirely, as middleware operates only on Next.js routes.

# Exact repository evidence

- `src/api/staff_performance_router.py` line 46 — `router = APIRouter()` (no router-level dependencies)
- `src/api/staff_performance_router.py` lines 146–151 — `get_staff_performance` signature with `Depends(jwt_auth)` only
- `src/api/staff_performance_router.py` lines 221–226 — `get_worker_performance` signature with `Depends(jwt_auth)` only
- `src/api/staff_performance_router.py` line 55–58 — uses `SUPABASE_SERVICE_ROLE_KEY` (bypasses Supabase RLS)
- `src/api/auth.py` — `jwt_auth` definition: validates JWT, returns `tenant_id`, does not check role
- `ihouse-ui/middleware.ts` lines 59–71 — ROLE_ALLOWED_PREFIXES (applies only to Next.js routes)

# Detailed evidence

**Router initialization — no router-level guards:**
```python
router = APIRouter()
```
No `dependencies=[Depends(require_role("admin"))]` or equivalent. Every endpoint in this router is responsible for its own guards. This router has no shared guard.

**Endpoint 1 — `GET /admin/staff/performance`:**
```python
@router.get(
    "/admin/staff/performance",
    tags=["admin"],
    summary="Aggregated staff performance metrics",
    responses={
        200: {"description": "Staff performance data"},
        401: {"description": "Missing or invalid JWT"},
        500: {"description": "Internal server error"},
    },
    openapi_extra={"security": [{"BearerAuth": []}]},
)
async def get_staff_performance(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),   # ← the only guard
    _client: Optional[Any] = None,
) -> JSONResponse:
```
The function signature contains exactly one security dependency: `Depends(jwt_auth)`. The response definitions include 401 but no 403. There is no 403 response definition, no role check in the function body, and no reference to a `role` field from the JWT.

**Endpoint 2 — `GET /admin/staff/performance/{worker_id}`:**
```python
@router.get(
    "/admin/staff/performance/{worker_id}",
    tags=["admin"],
    ...
)
async def get_worker_performance(
    worker_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),   # ← the only guard
    _client: Optional[Any] = None,
) -> JSONResponse:
```
Same pattern. No role check. No 403 path.

**What `jwt_auth` provides:**
`jwt_auth` in `src/api/auth.py` validates the JWT signature and expiry, and returns the `sub` claim as `tenant_id`. It does not extract, validate, or return the `role` claim. After `jwt_auth` runs, the endpoint function has no access to the JWT role without decoding the token again independently. Neither endpoint does this.

**The Supabase client used — RLS is bypassed:**
```python
def _get_supabase_client() -> Any:
    from supabase import create_client
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],  # ← service role key
    )
```
The `SUPABASE_SERVICE_ROLE_KEY` bypasses all Supabase Row Level Security policies. Even if RLS policies on the `tasks` table were configured to restrict access by JWT role, those policies would not apply to queries made with the service role key. There is no RLS mitigation for the missing application-layer role check.

**Data returned by the endpoints:**
For each worker in the tenant, the aggregate endpoint returns:
- `worker_id`
- `total_tasks_assigned`
- `total_tasks_completed`
- `completion_rate` (percentage)
- `avg_ack_minutes` (average time to acknowledge tasks)
- `sla_compliance_pct` (% of critical tasks acknowledged within 5 minutes)
- `tasks_per_day`
- `preferred_channel` (LINE/Telegram/etc — reveals worker's notification channel setup)
- `kind_breakdown` (task type distribution)

This data reveals internal operational patterns, individual worker performance, SLA compliance history, and notification infrastructure for the entire tenant workforce.

**What middleware.ts provides — and what it does not:**
```typescript
const ROLE_ALLOWED_PREFIXES: Record<string, string[]> = {
    owner:         ['/owner', '/dashboard'],
    worker:        ['/worker', '/ops', ...],
    cleaner:       ['/worker', '/ops'],
    ...
};
```
A `cleaner`-role user visiting `/admin/staff/performance` in the browser is redirected to `/no-access` by `middleware.ts` before the page loads. This correctly protects the frontend UI.

However, `middleware.ts` is a Next.js Edge middleware. It governs requests to Next.js routes. When a user makes a direct HTTP request to the FastAPI backend URL (e.g., `https://api.ihouse.example.com/admin/staff/performance`), that request never passes through Next.js middleware. It goes directly to the FastAPI router. At that point, only `jwt_auth` runs — and it passes any valid JWT regardless of role.

A valid JWT is obtained at login by any authenticated user. A cleaner logs in, receives a JWT with `role="cleaner"` and `tenant_id="<tenant>"`. They then make:
```
GET https://[backend-url]/admin/staff/performance
Authorization: Bearer <cleaner JWT>
```
The backend validates the JWT, extracts `tenant_id`, queries all tasks in the tenant, computes performance metrics for every worker, and returns the data. The cleaner's role field is never examined.

**Comparison with other admin routers:**
Other routers in the system include explicit role checks. For example, `admin_router.py` and `permissions_router.py` include checks like `if role not in ("admin", "manager"): raise HTTPException(403)`. The absence of this pattern in `staff_performance_router.py` is inconsistent with the broader pattern in the codebase. It appears to be an oversight during Phase 253 implementation, not a deliberate design choice.

# Contradictions

- Path prefix `/admin/staff/performance` signals admin-only access. Implementation enforces only authentication (any role).
- OpenAPI tag `["admin"]` groups this under admin documentation. Tags have no runtime enforcement.
- File header docstring (line 28) states "JWT auth required" — accurate. It does not mention role restriction. This omission in the docstring matches the omission in the implementation.
- Other routers in the codebase include explicit role checks. This router does not. The inconsistency is the strongest evidence that this is an oversight.
- The OpenAPI spec's `"security": [{"BearerAuth": []}]` annotation implies authentication but not authorization at the role level.

# What is confirmed

- Both endpoints use only `Depends(jwt_auth)` with no role check.
- `jwt_auth` does not return or validate the `role` claim.
- The Supabase client uses the service role key, bypassing any DB-level RLS.
- The frontend middleware blocks non-admin access to `/admin/` routes in the UI.
- The middleware does NOT protect direct HTTP calls to the FastAPI backend.
- The data returned includes sensitive workforce performance metrics for all workers in the tenant.

# What is not confirmed

- Whether any Supabase RLS policies on the `tasks` table use a JWT role claim from the anon key to restrict access. If the service role key were replaced with the anon key + user JWT, RLS could provide a secondary guard. But the current implementation uses the service role key and bypasses RLS.
- Whether any API gateway, reverse proxy, or infrastructure-level guard restricts access to `/admin/*` backend routes by role before requests reach FastAPI. If such a layer exists in production infrastructure, the application-layer gap may be mitigated externally.
- Whether any worker currently holds a JWT and knows the FastAPI backend URL to exploit this directly. This is an operational question, not a code question.
- Whether the frontend surface for staff performance is visible to non-admin roles at all — if no UI surfaces expose this data to workers, the attack surface requires knowledge of the backend URL and a valid JWT.

# Practical interpretation

Any authenticated user in the tenant — including field workers and owners — can retrieve complete workforce performance data by making a direct HTTP call to the FastAPI backend with their login JWT. This includes preferred notification channels (revealing how each worker is configured for SLA alerts), average acknowledgment times (revealing individual responsiveness patterns), and SLA compliance percentages (revealing performance gaps).

In a small operation with trusted staff, this may be low risk. In a multi-property operation with many workers of different trust levels, this exposes internal HR-sensitive performance data to all staff, regardless of role.

The fix is minimal: add a role check at the start of each endpoint body:
```python
# Example fix (not implemented — recorded here for reference only)
jwt_payload = decode_jwt(...)  # re-decode or pass through from jwt_auth
if jwt_payload.get("role") not in ("admin", "manager"):
    return make_error_response(403, ErrorCode.FORBIDDEN)
```
Or add `dependencies` at the router level using a role-checking dependency. This is a small, targeted fix.

# Risk if misunderstood

**If this is assumed protected because middleware blocks `/admin/` routes in the UI:** The API endpoint is unprotected. Any worker who knows the backend URL (common knowledge in staging environments) can query performance data for all coworkers.

**If this is treated as theoretical:** Staging environments often have relaxed security expectations. If the missing guard is not added before production deployment, it becomes a live exposure for any multi-role tenant with workers who have their own JWT.

**If a "fix" adds middleware.ts rules only (not backend guards):** Middleware changes do not protect direct API calls. The fix must be in the FastAPI endpoint — not the Next.js middleware.

# Recommended follow-up check

1. Read `src/api/auth.py` fully to see whether there is a role-checking utility function already defined that could be used as a `Depends()` here — to avoid building one from scratch.
2. Search for `Depends(require_admin)` or `Depends(require_role)` across all routers to find the pattern used elsewhere, and apply the same pattern here.
3. Search for any API gateway configuration (Railway, Nginx, Traefik) in deployment documentation to see if infrastructure-level route guards exist for `/admin/*` paths.
4. Check `src/api/admin_router.py` or `src/api/permissions_router.py` to find an existing role check pattern to replicate.
