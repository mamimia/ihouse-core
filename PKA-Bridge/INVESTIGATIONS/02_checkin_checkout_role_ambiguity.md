# Title

The `checkin_checkout` Role Exists in Three Places With Inconsistent Status

# Why this matters

`checkin_checkout` appears in the Act As actable role list, in the frontend routing table, in the task board, and in worker page logic — but it is absent from the canonical role definition. This ambiguity creates a gap between what the system will accept (Act As can issue a JWT with `role="checkin_checkout"`) and what the system is designed for (canonical roles don't include it). Any developer building role-based guards, middleware rules, or DB validators must understand exactly what category this role belongs to — otherwise they will either add it to canonical roles incorrectly or silently break the combined worker flow.

# Original claim

`checkin_checkout` exists as a frontend concept but is not a canonical backend role.

# Final verdict

PARTIAL

# Executive summary

The claim is partially correct but misleadingly incomplete. It is accurate that `checkin_checkout` is absent from `canonical_roles.py` and from `middleware.ts`'s route prefix matrix. But it is not a purely frontend concept. It appears in `act_as_router.py`'s actable role list — meaning an admin can issue a real JWT with `role="checkin_checkout"` through the Act As mechanism. It appears in `worker/page.tsx` as an explicit stored sub-role in `worker_roles[]`. It has a post-login route in `roleRoute.ts`. Its true status is: a recognized sub-role in the `worker_roles[]` array, reachable through Act As, with no canonical DB role entry and no middleware route prefix entry. The claim "frontend concept only" understates its backend presence.

# Exact repository evidence

- `src/services/canonical_roles.py` — `CANONICAL_ROLES` frozenset definition
- `src/api/act_as_router.py` line 53 — `_ACTABLE_ROLES` frozenset
- `ihouse-ui/middleware.ts` lines 59–67 — `ROLE_ALLOWED_PREFIXES` mapping
- `ihouse-ui/lib/roleRoute.ts` line 42 — post-login redirect map
- `ihouse-ui/app/(app)/worker/page.tsx` lines 74–111 — `resolveWorkerRole()` function
- `ihouse-ui/app/(app)/ops/checkin-checkout/page.tsx` — combined role hub page
- `ihouse-ui/app/(app)/act-as/page.tsx` line 27 — Act As route mapping
- `ihouse-ui/app/(app)/tasks/page.tsx` lines 354, 379, 388, 456 — task board handling

# Detailed evidence

**`canonical_roles.py` — `checkin_checkout` is absent:**
```python
CANONICAL_ROLES: frozenset[str] = frozenset({
    "admin", "manager", "ops", "owner", "worker",
    "cleaner", "checkin", "checkout", "maintenance",
})
```
Nine roles. `checkin_checkout` is not one of them. This is the authoritative role list for DB storage — `tenant_permissions.role` must match one of these values.

**`act_as_router.py` — `checkin_checkout` IS in `_ACTABLE_ROLES`:**
```python
_ACTABLE_ROLES = frozenset({
    "manager", "owner", "worker", "cleaner",
    "checkin", "checkout", "checkin_checkout", "maintenance",
})
```
An admin can issue a scoped Act As JWT with `role="checkin_checkout"`. This JWT is real — it is accepted by `jwt_auth` and carries a real `role` claim. The canonical roles restriction does not apply to Act As JWTs.

**`middleware.ts` — `checkin_checkout` has NO route prefix entry:**
```typescript
const ROLE_ALLOWED_PREFIXES: Record<string, string[]> = {
    owner:         ['/owner', '/dashboard'],
    worker:        ['/worker', '/ops', '/maintenance', '/checkin', '/checkout'],
    cleaner:       ['/worker', '/ops'],
    ops:           ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests'],
    checkin:       ['/checkin', '/ops/checkin'],
    checkout:      ['/checkout', '/ops/checkout'],
    maintenance:   ['/maintenance', '/worker'],
    identity_only: ['/welcome', '/profile', '/get-started', '/my-properties'],
};
```
`checkin_checkout` is not in this map. A JWT with `role="checkin_checkout"` would fall through to the default case in middleware — which redirects to `/no-access`. This means Act As sessions with `role="checkin_checkout"` cannot navigate to any route unless middleware has special handling for Act As tokens.

**`roleRoute.ts` — `checkin_checkout` HAS a post-login redirect:**
```typescript
checkin_checkout: '/ops/checkin-checkout',
```
This file maps JWT role values to post-login redirect destinations. `checkin_checkout` maps to `/ops/checkin-checkout`. This redirect only fires after a successful login — if middleware then blocks `/ops/checkin-checkout`, the session will loop or redirect to `/no-access`.

**`worker/page.tsx` — explicit sub-role handling:**
```typescript
// JWT role == "checkin_checkout" → explicit combined role (NOT a fallback)
// INVARIANT: A worker NEVER enters the 'checkin_checkout' surface unless their
// explicit stored worker_role or worker_roles includes 'checkin_checkout'.
```
The comment at lines 74–80 is definitive about intent: `checkin_checkout` is stored in `worker_roles[]` (the sub-role array in `tenant_permissions.permissions`), not in `tenant_permissions.role` (the canonical role field). When a worker's `worker_roles[]` includes `checkin_checkout`, the `resolveWorkerRole()` function routes them to the combined hub page.

**`/ops/checkin-checkout/page.tsx` — the hub page exists:**
The combined role hub page exists as a real route. It shows both check-in and check-out workflow cards in a single view. This page is the destination for workers whose `worker_roles[]` includes `checkin_checkout`.

**Structural summary:**
Two different systems reference `checkin_checkout`:
1. `tenant_permissions.role` — canonical DB role field. `checkin_checkout` is NOT valid here.
2. `tenant_permissions.permissions.worker_roles[]` — sub-role array. `checkin_checkout` IS valid here (no confirmed validator blocks it).

The Act As mechanism issues it directly in the JWT `role` claim — bypassing both of the above, since Act As JWTs are temporary and not backed by a DB role row.

# Contradictions

- `act_as_router.py` allows `checkin_checkout` as an actable role → a JWT can carry `role="checkin_checkout"`. But `canonical_roles.py` doesn't include it → any validation code checking `CANONICAL_ROLES` would reject it. These two files are in direct tension.
- `roleRoute.ts` expects `checkin_checkout` to produce a valid session at `/ops/checkin-checkout`. But `middleware.ts` has no prefix entry for this role → the middleware would block access to `/ops/checkin-checkout` for a JWT with `role="checkin_checkout"` unless Act As tokens are handled differently.
- The `worker/page.tsx` comment says "explicit stored worker_role" — implying it can appear in `worker_roles[]` from normal (non-Act As) DB storage. But it is not in `CANONICAL_ROLES`, so if any code path validates `worker_roles[]` values against `CANONICAL_ROLES`, it would be rejected at the point of storage.
- The claim in the original evidence that this is "a frontend concept" is contradicted by `act_as_router.py` and the worker page sub-role logic, both of which are backend-originated behaviors.

# What is confirmed

- `checkin_checkout` is absent from `CANONICAL_ROLES` in `canonical_roles.py`.
- `checkin_checkout` is present in `_ACTABLE_ROLES` in `act_as_router.py`.
- `checkin_checkout` has a post-login route in `roleRoute.ts` (`/ops/checkin-checkout`).
- The `/ops/checkin-checkout` hub page exists as a real frontend route.
- `worker/page.tsx` explicitly handles `checkin_checkout` as a sub-role from `worker_roles[]`.
- `checkin_checkout` is absent from `middleware.ts` route prefix matrix.
- `tasks/page.tsx` has `checkin_checkout`-specific handling in multiple places.

# What is not confirmed

- Whether `middleware.ts` has special handling for Act As tokens that bypasses the role prefix check. If it does, the middleware gap is not a real problem for Act As sessions. If it does not, Act As with `role="checkin_checkout"` would immediately redirect to `/no-access`.
- Whether any code path validates `worker_roles[]` values against `CANONICAL_ROLES`. If validation exists, `checkin_checkout` cannot be stored in `worker_roles[]` for real (non-Act As) users either.
- Whether any `tenant_permissions` DB row in any tenant currently has `checkin_checkout` in any field. This is the most operationally important unknown — is this theoretical or in active use?
- What happens at middleware when a real user (not Act As) logs in with JWT `role="worker"` but `worker_roles=["checkin_checkout"]` — how does the JWT `role` claim get set in this case? Is it set to `worker` (canonical) or `checkin_checkout` (sub-role)?

# Practical interpretation

In practice today, there are two ways a user can reach the `/ops/checkin-checkout` hub:
1. Act As session: an admin issues an Act As JWT with `role="checkin_checkout"`. This may fail at middleware unless middleware handles Act As tokens specially.
2. Worker sub-role: a worker with canonical role `worker` has `checkin_checkout` in their `worker_roles[]`. The `worker/page.tsx` `resolveWorkerRole()` function detects this and renders the combined hub. The JWT still carries `role="worker"` (a canonical role), so middleware passes.

Path 2 is the production-viable path. Path 1 (Act As with `checkin_checkout` as the JWT role) has a potential middleware gap that makes it non-functional without special handling.

`checkin_checkout` is best understood as: a worker sub-role that routes to a combined UI surface, not an independent canonical role.

# Risk if misunderstood

**Risk 1 — Adding `checkin_checkout` to `CANONICAL_ROLES`:** If a developer treats it as a first-class canonical role and adds it, they will need to add middleware route prefix entries, update the permissions DB schema, update all role guards, and update the Act As flow. This is a significant cross-cutting change with unclear benefit, since the sub-role pattern already works.

**Risk 2 — Ignoring it as "frontend only":** The Act As impersonation path and task board handling that explicitly accommodate it will be broken by any refactor that assumes `checkin_checkout` doesn't exist on the backend.

**Risk 3 — Assuming Act As with `checkin_checkout` is functional:** If the middleware gap is real (no special Act As handling), then Act As sessions with this role redirect to `/no-access` and QA cannot test the combined hub through impersonation.

# Recommended follow-up check

1. Read `ihouse-ui/middleware.ts` fully — specifically the section that handles `token_type: "act_as"` JWT claims. Determine whether Act As tokens bypass the role prefix check entirely.
2. Search for any validation code that checks `worker_roles[]` values against `CANONICAL_ROLES` — specifically in `permissions_router.py` or `staff_onboarding_router.py`.
3. Query the `tenant_permissions` table (or migration history) for any row where `permissions->>'worker_roles'` contains `checkin_checkout` — to determine if this is theoretical or actively stored.
