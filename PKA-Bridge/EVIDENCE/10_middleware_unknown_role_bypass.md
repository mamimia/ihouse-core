# Claim

Any JWT role that is not explicitly listed in `ROLE_ALLOWED_PREFIXES` and is not in `FULL_ACCESS_ROLES` passes through middleware with unrestricted route access.

# Verdict

PROVEN

# Why this verdict

Direct reading of `ihouse-ui/middleware.ts` lines 165–174 shows the access check is inside an `if (allowedPrefixes)` block. If `allowedPrefixes` is `undefined` — which occurs for any role not in `ROLE_ALLOWED_PREFIXES` — the block is skipped entirely and the middleware returns `NextResponse.next()`. This means an unrecognized role is not redirected to `/no-access`; it is granted unrestricted access to all protected routes.

# Direct repository evidence

- `ihouse-ui/middleware.ts` lines 59–67 — `ROLE_ALLOWED_PREFIXES` definition
- `ihouse-ui/middleware.ts` lines 70–71 — `FULL_ACCESS_ROLES = new Set(['admin', 'manager'])`
- `ihouse-ui/middleware.ts` lines 165–174 — the access check logic
- `ihouse-ui/middleware.ts` line 148 — role extraction from JWT payload
- `src/api/act_as_router.py` line 53 — `_ACTABLE_ROLES` includes `checkin_checkout`

# Evidence details

**The access check logic (lines 165–174):**
```typescript
const allowedPrefixes = ROLE_ALLOWED_PREFIXES[role];
if (allowedPrefixes) {
    const hasAccess = allowedPrefixes.some(prefix => pathname.startsWith(prefix));
    if (!hasAccess) {
        const defaultRoute = allowedPrefixes[0] || '/dashboard';
        return NextResponse.redirect(new URL(defaultRoute, request.url));
    }
}
// Falls through to NextResponse.next() ← UNRESTRICTED
const response = NextResponse.next();
```

If `role = "checkin_checkout"` (not in ROLE_ALLOWED_PREFIXES):
- `allowedPrefixes = undefined`
- `if (allowedPrefixes)` is `false`
- Entire access check block is skipped
- Execution falls through to `NextResponse.next()` with unrestricted access

**Roles not in ROLE_ALLOWED_PREFIXES:**
- `checkin_checkout` — present in `act_as_router._ACTABLE_ROLES`; absent from ROLE_ALLOWED_PREFIXES
- Any future novel role added to the backend without a corresponding middleware entry
- Any misspelled role value in a JWT (e.g., `"ADMIN"` vs `"admin"` — note: roles are lowercased at line 148, so this specific case is safe)

**Impact for `checkin_checkout` Act As sessions:**
In non-production environments, an admin can issue a JWT with `role="checkin_checkout"` via `POST /auth/act-as/start`. This JWT is valid. When the frontend stores it and navigates, middleware receives this role, finds no entry in `ROLE_ALLOWED_PREFIXES`, and lets all requests through. The Act As session with `checkin_checkout` has effectively unrestricted frontend route access — admin-level route access — despite being an impersonation of a limited worker sub-role.

# Conflicts or contradictions

- The middleware header comment says: "admin/manager have full access (not listed — they bypass checks)". The intent was that only admin and manager bypass the check. Unknown roles were not intended to bypass.
- Investigation 02 (this audit) previously stated that a `checkin_checkout` JWT "would likely fall to the default case (redirect to `/no-access`) in middleware." This was incorrect. Direct reading shows the opposite: unknown roles fall through to unrestricted access.

# What is still missing

- Whether any real Act As sessions with `checkin_checkout` have been started in staging.
- Whether this bypass affects any other production-path role token (all canonical roles are in ROLE_ALLOWED_PREFIXES, so production regular logins are not affected — only Act As sessions with non-canonical roles or future novel roles).

# Risk if misunderstood

If this bypass is not known, a developer adding a new role to `_ACTABLE_ROLES` without adding it to `ROLE_ALLOWED_PREFIXES` will inadvertently grant that role unrestricted frontend access in Act As sessions.
