# Claim

`checkin_checkout` exists as a frontend concept but is not a canonical backend role.

# Verdict

PARTIAL

# Why this verdict

The original claim is partially correct but materially incomplete. `checkin_checkout` is absent from `canonical_roles.py` — meaning it cannot appear in `tenant_permissions.role`. However, it is explicitly present in `act_as_router.py`'s actable role list, treated as an explicit JWT claim in frontend logic, and routed by both `roleRoute.ts` and `middleware.ts`. It occupies an in-between state: not a canonical DB role, but also not purely a frontend invention.

# Direct repository evidence

- `src/services/canonical_roles.py` — defines `CANONICAL_ROLES` frozenset
- `src/api/act_as_router.py` line 53 — `_ACTABLE_ROLES` frozenset
- `ihouse-ui/middleware.ts` — route prefix matrix
- `ihouse-ui/lib/roleRoute.ts` line 42 — post-login redirect map
- `ihouse-ui/app/(app)/worker/page.tsx` lines 74–111 — `resolveWorkerRole()` logic
- `ihouse-ui/app/(app)/act-as/page.tsx` line 27 — act-as route mapping
- `ihouse-ui/app/(app)/preview/page.tsx` line 39 — preview route mapping
- `ihouse-ui/app/(app)/tasks/page.tsx` lines 354, 379, 388, 456 — task board handling

# Evidence details

**`canonical_roles.py` — `checkin_checkout` is absent:**
```python
CANONICAL_ROLES: frozenset[str] = frozenset({
    "admin", "manager", "ops", "owner", "worker",
    "cleaner", "checkin", "checkout", "maintenance",
})
```
Nine roles. `checkin_checkout` is not one of them.

**`act_as_router.py` — `checkin_checkout` IS in `_ACTABLE_ROLES`:**
```python
_ACTABLE_ROLES = frozenset({
    "manager", "owner", "worker", "cleaner",
    "checkin", "checkout", "checkin_checkout", "maintenance",
})
```
An admin can issue a scoped Act As JWT with `role = "checkin_checkout"`. This means `checkin_checkout` can appear in a JWT `role` claim in the real system — just not in `tenant_permissions.role`.

**`middleware.ts` — `checkin_checkout` has no explicit route prefix entry:**
The route prefix matrix covers: admin, manager, owner, worker, cleaner, ops, checkin, checkout, maintenance, identity_only. `checkin_checkout` is not listed. A JWT with `role = "checkin_checkout"` would likely fall to the default case (redirect to `/no-access`) in middleware unless the JWT is an Act As token handled by a separate path.

**`roleRoute.ts` line 42 — `checkin_checkout` has a post-login route:**
```typescript
checkin_checkout: '/ops/checkin-checkout',
```
This is the redirect destination after login. But login would require a JWT with `role = "checkin_checkout"`, which can only come from Act As (since it's not in canonical_roles).

**`worker/page.tsx` comment at line 74–80:**
```
// JWT role == "checkin_checkout" → explicit combined role (NOT a fallback)
// INVARIANT: A worker NEVER enters the 'checkin_checkout' surface unless their
// explicit stored worker_role or worker_roles includes 'checkin_checkout'.
```
The comment says `worker_role` or `worker_roles[]` can contain `checkin_checkout`. This means the intent is for `checkin_checkout` to be stored in the `worker_roles[]` sub-role array in `tenant_permissions.permissions` — not as `tenant_permissions.role` (which is the canonical role field). These are two different fields.

**Structural clarification:**
- `tenant_permissions.role` = canonical role (must be in `CANONICAL_ROLES`)
- `tenant_permissions.permissions.worker_roles[]` = sub-role array (less strictly validated)

`checkin_checkout` appears to live only in the sub-role array, not the canonical role field. The Act As mechanism issues it directly as a JWT `role` claim, bypassing the canonical restriction.

# Conflicts or contradictions

- `act_as_router.py` allows `checkin_checkout` as an actable role, which means a JWT can carry it as a `role` claim. But `canonical_roles.py` does not include it, so it could fail any validation code that checks against `CANONICAL_ROLES`.
- `worker/page.tsx` treats `checkin_checkout` as an "explicit stored worker_role" that can come from `worker_roles[]` — but validation of `worker_roles[]` values is not confirmed as being enforced against `CANONICAL_ROLES`.
- `middleware.ts` has no prefix entry for `checkin_checkout`, which means a real JWT with `role = "checkin_checkout"` (from Act As) might fail route authorization on next page load unless the middleware handles Act As tokens differently.

# What is still missing

- Whether `middleware.ts` has special handling for Act As tokens that bypasses the role prefix check.
- Whether any validation code checks `worker_roles[]` values against `CANONICAL_ROLES` (which would reject `checkin_checkout`).
- Whether any real `tenant_permissions` row has ever stored `checkin_checkout` in any field, or whether this is purely theoretical/Act As only.
- What happens at the middleware layer when a real user (not in an Act As session) has `worker_roles: ["checkin_checkout"]` — how does their JWT `role` claim get set?

# Risk if misunderstood

If a developer builds role-based guards assuming `checkin_checkout` is a canonical role (like `cleaner` or `checkin`), they may add it to `CANONICAL_ROLES` without understanding the intentional separation between canonical DB roles and sub-role arrays. Conversely, if it is ignored as "frontend only," the Act As impersonation path and task board handling that explicitly accommodates it will be broken.

The ambiguity in `act_as_router.py` (allowing a non-canonical role in `_ACTABLE_ROLES`) is the clearest signal that this role's status was evolving and may not be fully resolved.
