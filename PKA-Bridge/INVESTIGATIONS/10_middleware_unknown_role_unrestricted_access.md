# Title

Middleware Grants Unrestricted Route Access to Any Role Not Explicitly Listed — Including `checkin_checkout` Act As Sessions

# Why this matters

The Next.js middleware is the primary frontend route guard. It is supposed to be the line that prevents a cleaner from seeing `/admin/*`, a checkout worker from seeing `/bookings`, and — critically — an unknown or novel role from accessing routes it was never intended to see. The code has a structural gap: the access check is wrapped in `if (allowedPrefixes)`. If the role is not in the prefix map, `allowedPrefixes` is `undefined`, the check is skipped, and the request passes through. Any role that is valid enough to carry a JWT but not mapped in `ROLE_ALLOWED_PREFIXES` has full, unrestricted frontend access. This gap affects `checkin_checkout` Act As sessions today and will affect any future role added to the backend without a corresponding middleware entry.

# Original claim

Any JWT role that is not explicitly listed in `ROLE_ALLOWED_PREFIXES` and is not in `FULL_ACCESS_ROLES` passes through middleware with unrestricted route access.

# Final verdict

PROVEN

# Executive summary

`middleware.ts` enforces route access via a lookup into `ROLE_ALLOWED_PREFIXES`. If the role is found, it checks whether the requested path starts with an allowed prefix and redirects if not. If the role is NOT found in the map, the check is skipped entirely, and the request proceeds. The roles `admin` and `manager` are handled first via `FULL_ACCESS_ROLES` and are intentionally unrestricted. All other roles should be in `ROLE_ALLOWED_PREFIXES`. But `checkin_checkout` — a role that can appear in a real JWT via the Act As system — is not in the map. An Act As session with `checkin_checkout` gets admin-level frontend route access, not the restricted access its name implies. An earlier audit summary stated that this role "would likely redirect to /no-access" in middleware — that was incorrect. Direct reading shows the opposite.

# Exact repository evidence

- `ihouse-ui/middleware.ts` lines 59–67 — `ROLE_ALLOWED_PREFIXES` map (all listed roles)
- `ihouse-ui/middleware.ts` lines 70–71 — `FULL_ACCESS_ROLES = new Set(['admin', 'manager'])`
- `ihouse-ui/middleware.ts` lines 148–174 — full role enforcement logic
- `ihouse-ui/middleware.ts` line 148 — `const role = ... payload.role ... .toLowerCase()`
- `ihouse-ui/middleware.ts` lines 165–174 — the gap: `if (allowedPrefixes) { ... } // falls through`
- `src/api/act_as_router.py` lines 51–54 — `_ACTABLE_ROLES` includes `checkin_checkout`
- `src/api/act_as_router.py` lines 186–198 — JWT payload structure for Act As tokens

# Detailed evidence

**The full `ROLE_ALLOWED_PREFIXES` map:**
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
Eight roles listed. `checkin_checkout` is not among them.

**`FULL_ACCESS_ROLES`:**
```typescript
const FULL_ACCESS_ROLES = new Set(['admin', 'manager']);
```
Two roles: admin and manager. `checkin_checkout` is not here either.

**The role enforcement block — the gap:**
```typescript
const role = (typeof payload?.role === 'string' ? payload.role : '').toLowerCase();

// Phase 862: empty/missing role → /no-access
if (!role) {
    if (pathname !== '/no-access') {
        return NextResponse.redirect(new URL('/no-access', request.url));
    }
    return NextResponse.next();
}

// If role is admin/manager, allow everything
if (FULL_ACCESS_ROLES.has(role)) {
    return NextResponse.next();
}

// Check if the role has access to this route
const allowedPrefixes = ROLE_ALLOWED_PREFIXES[role];
if (allowedPrefixes) {
    const hasAccess = allowedPrefixes.some(prefix => pathname.startsWith(prefix));
    if (!hasAccess) {
        const defaultRoute = allowedPrefixes[0] || '/dashboard';
        return NextResponse.redirect(new URL(defaultRoute, request.url));
    }
}

// ← If allowedPrefixes is undefined, execution reaches here
const response = NextResponse.next();  // Unrestricted access
response.headers.set('x-tenant-id', tenantId);
response.headers.set('x-user-role', role);
return response;
```

Step-by-step for `role = "checkin_checkout"`:
1. `role` is not empty → passes empty check
2. `FULL_ACCESS_ROLES.has("checkin_checkout")` → `false` → not admin/manager
3. `ROLE_ALLOWED_PREFIXES["checkin_checkout"]` → `undefined`
4. `if (allowedPrefixes)` → `if (undefined)` → `false` → block skipped
5. Execution falls through to `NextResponse.next()`
6. Request proceeds to any route, unrestricted

**The Act As JWT for `checkin_checkout`:**
```python
# From act_as_router.py lines 186-198
jwt_payload = {
    "sub": admin_user_id,
    "tenant_id": tenant_id,
    "role": body.target_role,     # = "checkin_checkout"
    "token_type": "act_as",
    "acting_session_id": session_id,
    "real_admin_id": admin_user_id,
    "auth_method": "act_as",
    "iat": now_ts,
    "exp": now_ts + body.ttl_seconds,
}
```
This is a valid JWT with `role: "checkin_checkout"`. When stored in a browser cookie and presented to middleware, it passes all of the early checks (not empty, not expired, not deactivated, not force_reset), then hits the `allowedPrefixes` check and falls through.

**How this actually manifests in an Act As session:**
1. Admin starts Act As session with `target_role = "checkin_checkout"`
2. Backend returns JWT with `role: "checkin_checkout"` (Act As is non-production only)
3. Frontend stores JWT in tab's sessionStorage (tab isolation via `staffApi.ts`)
4. User navigates in the Act As tab
5. Middleware receives requests from that tab with the Act As JWT
6. `role = "checkin_checkout"` → not in ROLE_ALLOWED_PREFIXES → unrestricted
7. The Act As session can navigate to `/admin/staff`, `/admin/owners`, `/tasks`, `/bookings` — everything admin sees

**The stated purpose of Act As — from `act_as_router.py` header:**
> "Admin-only capability for entering a scoped acting session with a target role's effective permissions. The admin performs real mutations through the role's operational flows."

The intent is to scope permissions DOWN to a specific role. For `checkin_checkout`, the intended scope is the combined check-in/check-out worker surface. In practice, the Act As session has BROADER route access than the admin's own session would grant a regular `checkin` or `checkout` role user.

**The `ROLE_ALLOWED_PREFIXES` comment at line 58:**
```typescript
// Phase 397: Role-to-allowed-route-prefix mapping
// admin/manager have full access (not listed — they bypass checks)
```
The comment explains why admin and manager are not listed. It does not contemplate any other role being absent. The design assumption was: all non-admin/manager roles are in the map. `checkin_checkout` violates this assumption.

**Does middleware check `token_type: "act_as"`?**
No. The middleware only extracts the `role` claim. It does not check `token_type`, `acting_session_id`, or any other Act As-specific claim. Act As tokens are processed identically to regular login tokens — only the `role` value is used for route enforcement.

# Contradictions

- Investigation 02 (this audit) stated: "`checkin_checkout` is absent from `middleware.ts`'s route prefix matrix — a JWT with `role='checkin_checkout'` would likely fall to the default case (redirect to `/no-access`)" — this was incorrect. The actual behavior is unrestricted access, not `/no-access`. The correction is documented here.
- The middleware header comment implies only admin/manager bypass checks. In reality, any unknown role also bypasses checks — a different mechanism producing a similar (but unintended) result.
- The Phase 862 comment says: "Previously, legacy tokens with no role claim got unrestricted admin access. Now, only explicit admin/manager roles get full access." Phase 862 fixed the empty-role bypass but introduced the unknown-role bypass with the same effect.

# What is confirmed

- `checkin_checkout` is not in `ROLE_ALLOWED_PREFIXES`.
- `checkin_checkout` is not in `FULL_ACCESS_ROLES`.
- The `if (allowedPrefixes)` check is skipped for any role absent from `ROLE_ALLOWED_PREFIXES`.
- Execution falls through to `NextResponse.next()` — unrestricted access.
- Act As can issue JWTs with `role: "checkin_checkout"` in non-production environments.
- Middleware does not check `token_type` — Act As JWTs are processed identically to regular JWTs for routing purposes.

# What is not confirmed

- Whether there are other roles that can appear in a JWT (via any mechanism) that are also absent from `ROLE_ALLOWED_PREFIXES`. The 8 canonical roles are all present. `checkin_checkout` is the only non-canonical role confirmed as reachable.
- Whether in practice the `checkin_checkout` Act As gap has been exploited or even used — it requires a non-production environment and admin access to trigger.
- Whether the frontend pages reachable via the bypass (e.g., `/admin/staff`) also check the JWT role server-side. If they do, a `checkin_checkout` Act As session would reach the page visually but receive 403 on all data loads. The net user experience might be an empty page rather than data exposure.

# Practical interpretation

In production this is not exploitable — Act As is blocked by returning 404 in the production environment. In staging and development, an admin can deliberately obtain unrestricted route access under the guise of an `checkin_checkout` Act As session. More importantly, the structural gap means any future role added to `_ACTABLE_ROLES` without a corresponding `ROLE_ALLOWED_PREFIXES` entry will silently have unrestricted frontend access.

The fix is straightforward: add `checkin_checkout` to `ROLE_ALLOWED_PREFIXES` with the appropriate prefixes (presumably `['/ops/checkin-checkout']`), and add a fallback default handler so that truly unknown roles redirect to `/no-access` rather than falling through.

# Risk if misunderstood

**If this is assumed safe because Act As is non-production only:** The structural gap remains in the codebase. Any future role added to `_ACTABLE_ROLES` inherits the bypass by default. This is a latent risk that materializes with every new role addition.

**If this is assumed to route to `/no-access`:** The actual behavior is opposite. Developers who believe unknown roles hit `/no-access` will not add missing entries to `ROLE_ALLOWED_PREFIXES`, perpetuating the bypass.

**If the bypass is assumed harmless because backend APIs will reject the wrong role:** This is partially true — backend endpoints that check the role claim will reject `checkin_checkout` for admin operations. But it gives the Act As session access to every frontend page, every admin dashboard component, and every UI state that renders based on route access rather than API response.

# Recommended follow-up check

1. Add `checkin_checkout: ['/ops/checkin-checkout']` to `ROLE_ALLOWED_PREFIXES` in `middleware.ts`.
2. Add a final `else` block: if `allowedPrefixes` is undefined after checking FULL_ACCESS_ROLES, redirect to `/no-access`. This closes the bypass for any future unknown role.
3. Audit `_ACTABLE_ROLES` in `act_as_router.py` — for every role listed there, verify it has an entry in `ROLE_ALLOWED_PREFIXES` that correctly scopes its intended access surface.
4. Test: start an Act As session with `target_role = "checkin_checkout"` in staging and verify the middleware routes correctly.
