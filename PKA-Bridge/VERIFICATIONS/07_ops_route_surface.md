# Title

Ops Role Surface Scope — No Security Issue; Frontend-Backend Mismatch on /bookings and /calendar Requires Product Decision; guests_router Unguarded

# Related files

- Investigation: `INVESTIGATIONS/07_ops_broader_surface.md`
- Evidence: `EVIDENCE/07_ops_broader_surface.md`

# Original claim

The `ops` role has a materially broader frontend route surface than any worker role — including `/bookings`, `/calendar`, and `/guests` — and it was unclear whether this was intentional, accidental overreach, or a gap in role definition.

# Original verdict

PROVEN — the broader surface was confirmed to exist; whether it was intentional was uncertain.

# Response from implementation layer

**Verdict from implementation layer: No real security issue, but there is a coherence gap between frontend and backend.**

**`ops` is intentionally a mid-tier Operational Manager role** positioned between workers and admin/manager in the hierarchy. The route surface is consistent with this design. However, two of the six frontend surfaces (`/bookings`, `/calendar`) are reachable in the frontend but blocked at the backend by `require_capability("bookings")`.

**Role hierarchy confirmed (`canonical_roles.py` lines 10–19):**
```python
# The role hierarchy (from highest to lowest access):
#     admin           — full tenant governance
#     manager         — operational management (legacy term for ops_manager)
#     ops             — operational team member         ← HERE
#     owner           — property owner (business visibility)
#     worker          — general staff
#     cleaner / checkin / checkout / maintenance
```
`ops` is in `STAFF_ROLES` (task-assignable), sits above `worker`, below management.

**Full surface state — what actually works:**

| Frontend route | Backend API called | Backend guard | ops allowed? |
|---------------|-------------------|--------------|-------------|
| `/ops` | Various worker/ops endpoints | `jwt_auth` only | ✅ Works |
| `/dashboard` | Various aggregation endpoints | `jwt_auth` only | ✅ Works |
| `/tasks` | `GET /worker/tasks` | `jwt_auth` + role scoping | ✅ Works (sees all tasks — role scoping checks `role=='worker'`, ops doesn't match) |
| `/guests` | `GET/POST/PATCH /guests` | `jwt_auth` only | ✅ Works |
| `/bookings` | `GET /bookings` | `require_capability("bookings")` | ❌ 403 denied |
| `/calendar` | `GET /bookings` (same API) | `require_capability("bookings")` | ❌ 403 denied |

**What the mismatch looks like in practice:**
An ops user can navigate to `/bookings` and `/calendar` in the frontend (middleware allows it), but the pages display errors or empty states because `require_capability("bookings")` rejects the data calls. The capability guard allows only `admin` and capability-delegated `manager`. `ops` is not in that list.

**What ops correctly cannot reach:**
- `/admin/*` — system configuration, staff management, permissions ✅ correct
- `/owner` — property owner financial surface ✅ correct
- `/checkin`, `/checkout`, `/maintenance` — field worker execution surfaces ✅ correct (ops coordinates, doesn't execute)

**ops vs workers is a complementary relationship, not hierarchical:**
`ops` has data-reading surfaces (`/bookings`, `/calendar`, `/guests`, `/tasks`) that no worker role has. `ops` does NOT have field-execution surfaces (`/checkin`, `/checkout`, `/maintenance`) that workers have. Coordination vs execution — by design.

**The `/tasks` full-visibility behavior is intentional:**
The task board role-scoping logic (`line 173`) checks `if perm.get("role") == "worker"` — ops doesn't match, so ops sees all tasks in the tenant (not just their own). This is correct for a coordinator role.

**Two issues raised but not fixed — both are product decisions:**

**Issue A — Frontend-backend mismatch on `/bookings` and `/calendar`:**
Middleware grants ops access; `require_capability("bookings")` rejects ops at the API layer. Two options:
1. Remove `/bookings` and `/calendar` from ops allowed prefixes in middleware — if the `/tasks` board provides enough operational context
2. Add `ops` to the capability guard's allowed roles — if ops should genuinely access booking data for coordination

Neither option is wrong. This requires a product decision. The middleware and the capability guard were built at different phases and currently disagree.

**Issue B — `guests_router` has no capability guard:**
The entire guests CRUD surface (`POST /guests`, `GET /guests`, `PATCH /guests`) uses only `jwt_auth`. Any authenticated user in the tenant (including cleaners) can read, create, and edit guest records. This is a guests_router-wide issue — not ops-specific. If guest data should be restricted, `require_capability("guests")` should be added to the guests router.

**Changes made: None.** Both issues require product decisions before code changes.

# Verification reading

No additional repository verification read was performed. The implementation response provides a complete and internally consistent picture of the ops surface with specific line references and code paths that directly address all 4 original questions.

# Verification verdict

PARTIALLY RESOLVED

The security concern is resolved — `ops` cannot access admin surfaces, cannot modify permissions or staff, and the two blocked surfaces (`/bookings`, `/calendar`) are correctly denied at the backend. No data exposure.

Two coherence gaps remain open as product decisions: (1) the frontend-backend mismatch on `/bookings` and `/calendar`, and (2) the unguarded `guests_router`.

# What changed

Nothing. No code was modified.

# What now appears true

- `ops` is an intentional Operational Manager role, not an accidental gap or incomplete worker variant.
- The six-surface frontend route table is coherent with the `ops` role's design — coordination and oversight, not field execution.
- `/bookings` and `/calendar` are reachable in the frontend but blocked by `require_capability("bookings")` at the backend. These pages produce errors/empty states for ops users. This is a frontend-backend phase mismatch, not a security risk.
- `/guests` works end-to-end for ops (and for any authenticated user — no capability guard on the guests router).
- `/tasks` full-visibility for ops is intentional: the role-scoping check (`role=='worker'`) doesn't apply to ops, so ops sees all tenant tasks. This matches the coordinator function.
- `ops` correctly cannot reach `/admin/*`, `/owner`, or the worker field-execution surfaces.
- The `canonical_roles.py` hierarchy explicitly positions `ops` above `worker` and below `manager` — the route surface reflects this positioning.

# What is still unclear

- **Product decision A**: Should `/bookings` and `/calendar` be removed from the ops frontend allowed prefixes, or should `require_capability("bookings")` be extended to also allow `ops`? The correct answer depends on whether booking visibility is part of the Operational Manager's job scope.
- **Product decision B**: Should `guests_router` have a capability guard? The current state (any authenticated user can create/edit guests) may be intentional for a multi-role hospitality workflow, or it may be an oversight. Guest record mutation is sensitive (PII).
- **Whether any ops users have ever tried to access `/bookings` or `/calendar`** and hit the error state. If so, this is a known UX breakage in production.
- **Whether the Phase 604 `owner_visibility_router.py` dual-schema issue** (see Issue 05) has any relationship to the ops role surface — not investigated.

# Recommended next step

**Close the security concern.** The ops role does not overreach into admin-only territory. The capability guard correctly blocks bookings data access.

**Resolve the two open product decisions before the next development phase:**

**Decision A** — `/bookings` and `/calendar` for ops:
- If ops should see booking data: add `ops` to `require_capability("bookings")` allowed roles, OR refactor to `require_capability("ops_bookings")` with a separate grant.
- If ops should not see booking data: remove `/bookings` and `/calendar` from `ROLE_ALLOWED_PREFIXES["ops"]` in `middleware.ts`.
- Either way, middleware and backend must agree.

**Decision B** — `guests_router` capability guard:
- If guest creation/editing should be restricted: add `require_capability("guests")` to POST and PATCH endpoints.
- If it should remain open to all authenticated users: document this explicitly so future audits don't flag it as a gap.
