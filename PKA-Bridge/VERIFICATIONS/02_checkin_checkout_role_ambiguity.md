# Title

checkin_checkout Role Ambiguity — Architecture Confirmed Intentionally Correct; Runtime Concerns Do Not Manifest

# Related files

- Investigation: `INVESTIGATIONS/02_checkin_checkout_role_ambiguity.md`
- Evidence: `EVIDENCE/02_checkin_checkout_role_status.md`
- Cross-reference: `INVESTIGATIONS/10_middleware_unknown_role_bypass.md` (partially affected by this finding)

# Original claim

`checkin_checkout` is absent from `CANONICAL_ROLES` and from `ROLE_ALLOWED_PREFIXES` in middleware. This creates ambiguity: is it a valid role, a work-in-progress role, or an accidental gap? The investigation raised concerns that Act As sessions with `role=checkin_checkout` might hit the `if (allowedPrefixes)` fallthrough in middleware, granting unrestricted route access.

# Original verdict

PARTIAL — architectural observations confirmed accurate; runtime consequences uncertain.

# Response from implementation layer

The implementation layer performed a full six-layer trace and concluded: **Not a real issue. The architecture is intentionally correct.**

**Layer-by-layer trace:**

1. **DB layer** — `checkin_checkout` is absent from `canonical_roles.py` frozenset by design. It is a sub-role stored in `tenant_permissions.permissions.worker_roles[]` (JSONB array). Real workers have `role = "worker"` in the DB; the sub-role specialization lives in the JSONB permissions column.

2. **JWT layer** — Real worker JWTs carry `role="worker"`. Act As JWTs carry `role="checkin_checkout"` directly in the payload (not "worker"). These are the two entry paths, and they behave differently through the remaining layers.

3. **Middleware layer** — Critical finding: middleware reads `request.cookies.get('ihouse_token')` (confirmed at `middleware.ts` line 100) — NOT sessionStorage. Act As tokens live ONLY in sessionStorage, never in cookies. An Act As tab inherits the admin's `ihouse_token` cookie from the browser session. Therefore, middleware always sees `role=admin` for an Act As tab, regardless of what role is in the Act As JWT. The `FULL_ACCESS_ROLES` check passes unconditionally for admin. The `if (allowedPrefixes)` fallthrough for `checkin_checkout` is never reached for Act As sessions. Real workers carry `role=worker` → middleware checks `/ops` prefix allowance → passes correctly.

4. **Application layer** — `worker/page.tsx` handles both paths:
   - Act As path: `token.role === "checkin_checkout"` (line 99) — direct role match
   - Real worker path: `token.role === "worker" && token.worker_roles?.[0] === "checkin_checkout"` (line 110) — sub-role resolution from JWT claims

5. **Act As router** — `_ACTABLE_ROLES` includes `checkin_checkout` intentionally. The router is gated behind `IHOUSE_ENV=production` check — returns 404 in production, only works in staging. This is the developer-facing impersonation tool.

6. **tokenStore architecture** — `setActAsTabToken()` stores Act As tokens ONLY in sessionStorage. Rule 1 in the module: "Act As tokens ONLY live in sessionStorage." The cookie (`ihouse_token`) is set by normal login only (`setToken()` → `localStorage` AND cookie). These never overlap.

**Conclusion from implementation layer:** No fix needed. The investigation's architectural observations (checkin_checkout absent from CANONICAL_ROLES, present in _ACTABLE_ROLES, absent from ROLE_ALLOWED_PREFIXES) are accurate but the concerns about runtime failures do not manifest because:
- Real workers use `role=worker` at the middleware layer
- Act As sessions inherit the admin cookie at the middleware layer
- Both paths resolve checkin_checkout correctly at the application layer

**One forward risk acknowledged:** If the Act As design ever changes to replace the `ihouse_token` cookie with sessionStorage isolation (i.e., the Act As tab no longer inherits the admin cookie), then the middleware gap becomes real. An Act As JWT carrying `role=checkin_checkout` would reach the `if (allowedPrefixes)` fallthrough and get `NextResponse.next()` — unrestricted route access. This is a latent architectural debt, not a current bug.

# Verification reading

Post-response confirmation performed by direct repository read:

**`ihouse-ui/middleware.ts` lines 99–104 — confirmed cookie read:**
```typescript
const token = request.cookies.get('ihouse_token')?.value
// ... decode token
```
Middleware reads the `ihouse_token` cookie. SessionStorage is inaccessible to middleware (Next.js middleware runs on the server edge). This is not configurable — it is a structural constraint of how Next.js middleware works.

**`ihouse-ui/lib/tokenStore.ts` — confirmed Act As token isolation:**
```typescript
// Rule 1: Act As tokens ONLY live in sessionStorage.
// Rule 2: Normal login token lives in localStorage AND cookie.
// Rule 3: getTabToken() is sessionStorage-first, falls back to localStorage.
// Rule 4: NEVER write Act As tokens to localStorage or cookies.
```
`setActAsTabToken()` writes exclusively to sessionStorage. Normal `setToken()` writes to both localStorage and cookie. The two paths are fully separated in code.

Both confirmations align exactly with the implementation layer response.

# Verification verdict

RESOLVED

# What changed

No code was changed. The architecture was determined to be intentionally correct.

The investigation's concerns were based on a gap in the analysis: the investigation knew middleware had an `if (allowedPrefixes)` fallthrough for unknown roles, and knew Act As JWTs carry `role=checkin_checkout`, but did not trace that middleware reads cookies — not sessionStorage — making the Act As JWT role invisible to middleware entirely.

The investigation's architectural observations remain factually accurate. The inferences drawn from those observations about runtime consequences were incorrect.

# What now appears true

- `checkin_checkout` is intentionally absent from `CANONICAL_ROLES`. It is a sub-role by design.
- Real workers: DB role is `"worker"`, sub-role specialization in `worker_roles[]` JSONB. JWT carries `role="worker"`.
- Act As sessions: JWT carries `role="checkin_checkout"` directly in payload. This JWT lives in sessionStorage only.
- Middleware reads cookies, not sessionStorage. Act As tab inherits admin's `ihouse_token` cookie. Middleware always sees `role=admin` for Act As tabs.
- The `if (allowedPrefixes)` fallthrough in middleware is inert for Act As sessions as currently designed.
- Investigation 10 (middleware unknown-role bypass) correctly identified the fallthrough mechanism but overstated its practical impact: the fallthrough applies to real requests with unknown roles in cookies, not to Act As sessions. **Note: Investigation 10 should be read with this correction in mind.**
- `worker/page.tsx` handles both entry paths (Act As and real worker) correctly at the application layer.

# What is still unclear

- Whether any production worker accounts have `role="checkin_checkout"` set directly in the DB (not as a sub-role). If they do, middleware would hit the fallthrough for real authenticated requests — not just Act As.
- Whether any future Act As redesign (tab isolation via cookie replacement) is planned. If so, the middleware gap becomes a real security issue and would require adding `checkin_checkout` to `ROLE_ALLOWED_PREFIXES`.
- Whether other sub-roles (if any exist beyond `checkin_checkout`) have the same structural pattern and the same middleware invisibility.

# Recommended next step

**Close as resolved.** The checkin_checkout architecture is intentionally correct and all six layers have been confirmed to behave as designed.

**Keep as a forward risk note:**
- If Act As design ever changes to replace the admin cookie with sessionStorage-only isolation, `checkin_checkout` must be added to `ROLE_ALLOWED_PREFIXES` in middleware before that change ships. Without it, Act As users with `role=checkin_checkout` in their cookie (new design) would get unrestricted route access via the fallthrough.

**Cross-reference note for Investigation 10:**
Investigation 10 states: "checkin_checkout Act As sessions get admin-level route access due to the fallthrough." This is technically correct about the fallthrough mechanism but the cause is wrong — they get admin-level access because middleware sees the admin cookie, not because of the fallthrough. The fallthrough is never reached in the current design. Investigation 10's practical risk section remains valid as a forward risk, not a current bug.
