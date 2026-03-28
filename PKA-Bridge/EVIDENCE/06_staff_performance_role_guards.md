# Claim

`staff_performance_router` lacks adequate role guards and is exposed more broadly than intended.

# Verdict

PROVEN

# Why this verdict

Both endpoints in `src/api/staff_performance_router.py` use only `Depends(jwt_auth)` for authorization. `jwt_auth` validates that a JWT exists and returns `tenant_id` from its `sub` claim. It does not check the `role` claim. No secondary role check exists in either endpoint body. The endpoints are mounted under `/admin/staff/performance` — a path that implies admin-only access — but any valid JWT holder (any role) can call them.

# Direct repository evidence

- `src/api/staff_performance_router.py` lines 146–151 — `get_staff_performance` signature
- `src/api/staff_performance_router.py` lines 221–226 — `get_worker_performance` signature
- `src/api/staff_performance_router.py` line 46 — `router = APIRouter()` — no prefix, no dependencies at router level
- `src/api/auth.py` — `jwt_auth` definition (validates JWT, returns `tenant_id`, does not check role)

# Evidence details

**Endpoint 1 — `GET /admin/staff/performance`:**
```python
@router.get(
    "/admin/staff/performance",
    tags=["admin"],
    ...
)
async def get_staff_performance(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    _client: Optional[Any] = None,
) -> JSONResponse:
```

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
    tenant_id: str = Depends(jwt_auth),   # ← only guard
    _client: Optional[Any] = None,
) -> JSONResponse:
```

Neither endpoint body contains a role check. There is no `if jwt_payload.get("role") not in ("admin", "manager"): raise HTTPException(403)` or equivalent.

**What `jwt_auth` provides:**
`jwt_auth` decodes the JWT, validates the `exp` claim and the `iss` claim, and returns the `tenant_id` from `sub`. It does not extract or validate the `role` claim. The role enforcement burden falls on each individual router — and this router does not exercise it.

**What this means at runtime:**
A cleaner (role=`cleaner`) with a valid JWT can call:
```
GET /admin/staff/performance
```
and receive aggregated metrics for all workers in the tenant — task counts, completion rates, SLA compliance percentages, preferred notification channels. A checkout worker or guest-facing token holder would similarly be able to call this endpoint if they hold a valid internal JWT.

**Data returned:**
The endpoint returns for each worker: `worker_id`, `total_tasks_assigned`, `total_tasks_completed`, `completion_rate`, `avg_ack_minutes`, `sla_compliance_pct`, `tasks_per_day`, `preferred_channel`, `kind_breakdown`. This is internal operational data that reveals staffing patterns, SLA violations, and notification preferences across the entire tenant.

**Router-level dependencies:**
```python
router = APIRouter()
```
No `dependencies=[Depends(require_admin)]` or equivalent is set at the router level. Each endpoint is individually responsible for its own guards.

**Path tag is `["admin"]` but tag is non-enforcing:**
The OpenAPI tag `"admin"` is for documentation grouping only. FastAPI does not enforce access based on tags.

# Conflicts or contradictions

- The endpoint URLs (`/admin/staff/performance`) and OpenAPI tags (`admin`) signal admin-only intent. The implementation does not enforce this.
- Other admin routers in the system (e.g., `admin_router.py`, `permissions_router.py`) include explicit role checks — this router does not. The inconsistency suggests this was an oversight rather than deliberate design.
- The docstring in the file header (line 28) states "JWT auth required" — accurate. It does not mention role restriction — an omission that may or may not be intentional.

# What is still missing

- Whether Supabase RLS policies on the `tasks` table restrict access by role. If RLS is enforced at the DB level using the JWT `role` claim, then even without an application-layer check, a cleaner's JWT would be rejected by Supabase before task data is returned. However, the router uses the `SUPABASE_SERVICE_ROLE_KEY` (line 56), which bypasses RLS entirely.
- Whether the route `/admin/staff/performance` is accessible via middleware.ts for non-admin roles. If middleware blocks non-admin roles from `/admin/*` prefixes before the request reaches the FastAPI backend, the application-layer missing guard is mitigated at the edge.
- Whether any frontend surface exposes this endpoint to non-admin roles.

**Important caveat on middleware mitigation:**
`middleware.ts` blocks non-admin, non-manager roles from `/admin/*` routes on the Next.js frontend. However, this only protects the frontend route — it does not protect the FastAPI API endpoint itself. Any direct HTTP call to `https://[backend-url]/admin/staff/performance` with a valid JWT (from any role) bypasses middleware entirely.

# Risk if misunderstood

If the system is considered secure because middleware blocks non-admin access to `/admin/` routes, the missing API-layer role guard may go unnoticed. The FastAPI endpoint is directly accessible to any valid JWT holder who makes HTTP requests outside the frontend — including during Act As sessions, automation, or external API access. A worker's JWT obtained from the frontend auth flow is sufficient to call this endpoint directly and retrieve performance data for all coworkers in the tenant.
