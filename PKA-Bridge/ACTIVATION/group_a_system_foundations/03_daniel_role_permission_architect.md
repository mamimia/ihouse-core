# Activation Memo: Daniel — Role & Permission Architect

**Phase:** 971 (Group A Activation)
**Date:** 2026-04-02
**Grounded in:** Direct reading of ihouse-core repository (canonical_roles.py, middleware.ts, auth.py, roleRoute.ts, main.py)

---

## 1. What in the Current Real System Belongs to This Domain

Daniel's domain is the authorization model — who can see what, who can do what, and why. The real system has:

- **9 canonical roles** in canonical_roles.py: admin, manager, ops, owner, worker, cleaner, checkin, checkout, maintenance (plus identity_only as a system state)
- **Role classifications**: FULL_ACCESS_ROLES (admin, manager), STAFF_ROLES (worker, cleaner, checkin, checkout, maintenance, ops), INVITABLE_ROLES (all except admin)
- **Frontend edge middleware** (middleware.ts) enforcing route access by role with deny-by-default policy
- **Backend JWT auth** (auth.py) with identity extraction, role resolution from tenant_permissions, and dev-mode bypass
- **Delegated capabilities** for managers (7 capabilities: financial, staffing, properties, bookings, maintenance, settings, intake)
- **Worker sub-roles** stored in tenant_permissions.permissions.worker_roles[]
- **Role-based landing page routing** (roleRoute.ts) directing each role to its appropriate surface
- **Preview-as and Act-as** systems with separate permission scoping

## 2. What Appears Built

- **Canonical role registry**: Single source of truth in canonical_roles.py. Roles are classified into FULL_ACCESS, STAFF, INVITABLE sets. This is clean and authoritative.
- **Frontend route access matrix**: middleware.ts maps route prefixes to allowed roles. Deny-by-default — unrecognized roles get no access. Public routes explicitly whitelisted. JWT validated at edge with expiry, deactivation, and force-reset checks.
- **Backend identity resolution**: auth.py extracts full identity (user_id, tenant_id, role, email, is_active, is_acting, acting_session_id) from JWT. Supports both legacy (sub=tenant_id) and new (sub=user_id, tenant_id explicit) token formats.
- **Role-based landing routing**: roleRoute.ts correctly routes: admin→/dashboard, manager→/manager, ops→/ops, cleaner→/ops/cleaner, checkin→/ops/checkin, checkout→/ops/checkout, checkin_checkout→/ops/checkin-checkout, maintenance→/ops/maintenance, owner→/owner, identity_only→/welcome.
- **Preview mode permission scoping**: PreviewModeMiddleware (Phase 866) blocks all mutations when admin uses X-Preview-Role. Only read methods pass. Exempt paths defined.
- **Act-as dual attribution**: ActAsAttributionMiddleware (Phase 869) captures real_admin_id on every mutation during act-as session. Best-effort — failures don't block response.
- **Unknown role fallback**: roleRoute.ts sends unknown roles to /dashboard. middleware.ts's deny-by-default means an unknown role cannot reach most routes.

## 3. What Appears Partial

- **API-level capability enforcement**: The delegated capability model for managers (7 capabilities) is defined. middleware.ts gives managers FULL_ACCESS to routes. But whether individual API routers check for specific capabilities (e.g., financial_router checks `financial` capability before serving data) needs router-by-router verification. The gap between route access (manager can reach /financial) and API enforcement (manager needs `financial` capability) is the key concern from the original SYSTEM_MAP.
- **checkin_checkout combined role**: This is a frontend routing concept in roleRoute.ts. Backend canonical_roles.py does not include it. A worker with worker_roles: ['checkin', 'checkout'] gets routed to /ops/checkin-checkout. But how the backend resolves this worker's permissions for task filtering and endpoint access needs confirmation.
- **Worker sub-role to task routing**: Workers receive tasks based on worker_roles[] matching task kind. The mapping (cleaner→CLEANING, checkin→CHECKIN_PREP, checkout→CHECKOUT_VERIFY, maintenance→MAINTENANCE) is implemented in task_writer.py via staff_property_assignments. But whether the frontend correctly filters the task board to show only role-appropriate tasks needs verification.

## 4. What Appears Missing

- **Role guard audit across 134 routers**: No systematic audit of which routers enforce role checks and which are open to any authenticated user. With 134 routers, some may lack role guards entirely.
- **Capability check inventory**: No centralized list of which endpoints check which manager capabilities. Capability enforcement is likely scattered across individual routers.
- **Role addition protocol**: No documented or enforced process for adding a new canonical role. canonical_roles.py is the source of truth, but adding a role there doesn't automatically update middleware.ts route matrix, roleRoute.ts routing, or task_writer.py sub-role mapping.

## 5. What Appears Risky

- **Route access vs API enforcement gap**: A manager with route access to /financial but without the `financial` delegated capability will reach the page but get denied by the API. The user experience of this gap (blank page? error component? silent failure?) is undefined unless Talia's interaction architecture addresses it.
- **Unknown role in roleRoute.ts → /dashboard**: If a user has an unrecognized role string, roleRoute.ts sends them to /dashboard. middleware.ts should block this at edge, but if the role string is valid in JWT but not in CANONICAL_ROLES, the behavior depends on middleware implementation. This is the Investigation #10 concern — is the unknown role truly rejected or just routed to a default?
- **Dev mode bypass**: auth.py's `IHOUSE_DEV_MODE=true` skips JWT verification entirely, returning "dev-tenant". This is blocked in production by env_validator.py, but if the validator fails to load, dev mode in production would bypass all auth.
- **Settlement and financial endpoints role guards**: The settlement routers (checkin_settlement, checkout_settlement, deposit_settlement) handle money operations. Whether these have explicit role guards (not just "any authenticated user") is critical and unverified.

## 6. What Appears Correct and Worth Preserving

- **Single source of truth**: canonical_roles.py as the authoritative role registry is a strong pattern. Role classifications (FULL_ACCESS, STAFF, INVITABLE) provide semantic grouping.
- **Deny-by-default at edge**: middleware.ts's approach of explicitly listing allowed roles per route prefix and blocking everything else is the correct security posture.
- **Token isolation by surface**: api.ts (admin) vs staffApi.ts (worker) prevents cross-surface token leakage. Act-as sessions use sessionStorage only.
- **Preview mode as server-enforced**: PreviewModeMiddleware blocks mutations at the HTTP method level. The admin cannot accidentally mutate data during preview. This is structurally safe.
- **JWT expiry and deactivation at edge**: middleware.ts checks token expiry, is_active flag, and force_password_reset at every request. Revocation is immediate.

## 7. What This Role Would Prioritize Next

1. **Audit settlement and financial router role guards**: These handle money. Confirm they require admin or manager+financial capability, not just any authenticated user.
2. **Map the manager capability enforcement pattern**: Sample 5 capability-gated routers and confirm the enforcement is consistent (same decorator/check pattern).
3. **Verify unknown role rejection end-to-end**: Send a request with a non-canonical role in the JWT and trace what happens at middleware.ts, then at roleRoute.ts, then at a protected API endpoint.

## 8. Dependencies on Other Roles

- **Nadia**: Daniel needs Nadia to verify that the role guard code in specific routers is actually executed (not just defined but unreachable)
- **Elena**: Daniel needs Elena to verify that tenant_permissions role values in the database match canonical_roles.py — if stale data has non-canonical roles, the unknown-role risk is real
- **Larry**: Daniel needs Larry to sequence the router audit — 134 routers is a large surface, needs prioritization
- **Talia (Group B)**: Daniel's findings about route-access vs API-enforcement gaps directly feed Talia's interaction architecture for capability-gated experiences

## 9. What the Owner Most Urgently Needs to Understand

The role model is well-designed at its core — canonical_roles.py, deny-by-default middleware, and token isolation are strong foundations. The risk is not in the design but in the **enforcement gaps across 134 routers**. With the system growing from 53 to 134 routers, the surface area for missing or inconsistent role guards has increased significantly. The highest-priority verification is whether the settlement and financial mutation endpoints have explicit role guards — these handle money, and a missing guard means any authenticated user could potentially call them.
