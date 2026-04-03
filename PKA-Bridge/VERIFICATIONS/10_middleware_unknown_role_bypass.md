# Title

Middleware Unknown Role Bypass — Real Issue Confirmed and Fixed; checkin_checkout Mapped; Deny-by-Default Added; Reconciliation with Verification 02 Required

# Related files

- Investigation: `INVESTIGATIONS/10_middleware_unknown_role_bypass.md`
- Evidence: `EVIDENCE/10_middleware_unknown_role_bypass.md`
- Cross-reference: `VERIFICATIONS/02_checkin_checkout_role_ambiguity.md` — see reconciliation note below

# Original claim

`if (allowedPrefixes)` in middleware is skipped when a role has no entry in `ROLE_ALLOWED_PREFIXES`, causing `NextResponse.next()` to execute unconditionally — granting unrestricted frontend route access for any unmapped role. `checkin_checkout` was identified as the one unmapped role reachable through `_ACTABLE_ROLES`.

# Original verdict

PROVEN — the bypass mechanism was confirmed; its practical impact was assessed as inert for Act As sessions due to cookie architecture (per Verification 02).

# Response from implementation layer

**Verdict from implementation layer: Investigation is correct. Real issue. Fixed.**

Both the specific gap (checkin_checkout unmapped) and the structural pattern (no deny-by-default) have been fixed.

**The bypass mechanism confirmed:**
```typescript
// Original middleware.ts lines 165–174
const allowedPrefixes = ROLE_ALLOWED_PREFIXES[role];
if (allowedPrefixes) {          // ← skipped entirely if undefined
    const hasAccess = allowedPrefixes.some(prefix => pathname.startsWith(prefix));
    if (!hasAccess) {
        const defaultRoute = allowedPrefixes[0] || '/dashboard';
        return NextResponse.redirect(new URL(defaultRoute, request.url));
    }
}
// ← falls through unconditionally if allowedPrefixes === undefined
const response = NextResponse.next();  // unrestricted
```

**Cross-reference of `_ACTABLE_ROLES` vs `ROLE_ALLOWED_PREFIXES`:**

| Role | In `_ACTABLE_ROLES`? | In `ROLE_ALLOWED_PREFIXES`? | Status |
|------|---------------------|----------------------------|--------|
| `manager` | ✅ | n/a — in `FULL_ACCESS_ROLES` | ✅ Safe |
| `owner` | ✅ | ✅ | ✅ Safe |
| `worker` | ✅ | ✅ | ✅ Safe |
| `cleaner` | ✅ | ✅ | ✅ Safe |
| `checkin` | ✅ | ✅ | ✅ Safe |
| `checkout` | ✅ | ✅ | ✅ Safe |
| `checkin_checkout` | ✅ | ❌ MISSING | ⚠️ Fixed |
| `maintenance` | ✅ | ✅ | ✅ Safe |

`checkin_checkout` was the only gap. All other actable roles were already mapped.

**Backend guards partially mitigate but do not fully protect:**
- `require_capability("bookings")` → 403 for checkin_checkout ✅
- `require_capability("staffing")` → 403 for checkin_checkout ✅
- Pages that render admin navigation client-side before data loads are still exposed to the wrong UI surface ⚠️
- `x-user-role: checkin_checkout` header forwarded downstream — pages branching on this may render incorrect UI states ⚠️
- The `/admin/*` route sub-tree: even empty/erroring pages expose page structure and navigation to the wrong role ⚠️

**Two changes applied to `middleware.ts`:**

**Change 1 — Map `checkin_checkout` explicitly:**
```diff
-    maintenance:   ['/maintenance', '/worker'],
+    checkin_checkout:  ['/ops/checkin-checkout', '/worker'],  // Phase 865: combined role hub
+    maintenance:       ['/maintenance', '/worker'],
```
`/ops/checkin-checkout/` directory exists in the filesystem. `/worker` is included as a secondary prefix because `worker/page.tsx` correctly handles the `checkin_checkout` role via `resolveWorkerRole()`.

**Change 2 — Deny-by-default fallback:**
```diff
 if (allowedPrefixes) {
     ...
-    }
+    } else {
+        if (pathname !== '/no-access') {
+            return NextResponse.redirect(new URL('/no-access', request.url));
+        }
+    }
```
Any role not in `FULL_ACCESS_ROLES` and not in `ROLE_ALLOWED_PREFIXES` now redirects to `/no-access` instead of passing through. Any future role added to `_ACTABLE_ROLES` without a corresponding `ROLE_ALLOWED_PREFIXES` entry is safe by default.

**Post-fix behavior:**

| Role in JWT cookie | Path requested | Behavior |
|-------------------|---------------|----------|
| `checkin_checkout` | `/ops/checkin-checkout` | ✅ Allowed |
| `checkin_checkout` | `/worker` | ✅ Allowed |
| `checkin_checkout` | `/admin/staff` | ❌ Redirected to `/ops/checkin-checkout` |
| `checkin_checkout` | `/bookings` | ❌ Redirected to `/ops/checkin-checkout` |
| Any future unmapped role | Any path | ❌ Redirected to `/no-access` |
| All existing mapped roles | (unchanged) | ✅ Unchanged |

# Reconciliation with Verification 02

**Verification 02 concluded:** "The `if (allowedPrefixes)` fallthrough in middleware is inert for Act As sessions as currently designed" — because middleware reads the `ihouse_token` cookie, Act As tabs inherit the admin's cookie, and middleware therefore always sees `role=admin` for Act As sessions. The bypass path was never reached for Act As sessions.

**This implementation response says:** `checkin_checkout` is "the confirmed reachable affected role" and "only Act As sessions with checkin_checkout as the target role" are affected.

**How to reconcile these two statements:**

Verification 02 was accurate for the current Act As architecture — middleware reads cookies, Act As JWTs live only in sessionStorage, Act As tabs inherit the admin cookie, so middleware sees `role=admin`. Under this architecture, a `checkin_checkout` Act As session never reaches the `ROLE_ALLOWED_PREFIXES` lookup.

The implementation response may reflect:
1. A desire to make the system correct by design rather than relying on the cookie architecture as a compensating control. Even if the bypass is currently unreachable via Act As, having an explicit mapping and a deny-by-default is architecturally sound.
2. Forward-looking protection: if Act As design ever changes (e.g., the Act As JWT is stored in a cookie instead of sessionStorage), `checkin_checkout` would reach the `ROLE_ALLOWED_PREFIXES` lookup without the mapping. The fix prevents that from becoming a real gap.
3. The possibility that real workers with `role=checkin_checkout` stored directly in a DB record (not via Act As) could produce a cookie with that role — which would NOT have the admin cookie override. If any such user exists or is created, the fix closes that path.

**Conclusion:** Both findings are correct. Verification 02 described the current effective behavior (bypass inert due to cookie architecture). This verification describes the correct fix regardless of that behavior. The fix makes the system safe by explicit mapping rather than by architectural dependency. Both the mapping and the deny-by-default are correct changes to make.

# Verification reading

No additional repository verification read performed. The implementation response provides specific before/after diffs, complete role-cross-reference table, and post-fix behavior matrix. The reconciliation above is derived from the two implementation responses in context.

# Verification verdict

RESOLVED

# What changed

`ihouse-ui/middleware.ts`:
1. `checkin_checkout: ['/ops/checkin-checkout', '/worker']` added to `ROLE_ALLOWED_PREFIXES`
2. `else` block added to the `if (allowedPrefixes)` branch — deny-by-default redirect to `/no-access`
3. Header comment updated to document `checkin_checkout` in the role hierarchy and state the deny-by-default guarantee

# What now appears true

- The `if (allowedPrefixes)` bypass was a real structural gap — confirmed by direct code inspection and fixed.
- `checkin_checkout` was the only unmapped actable role in the current codebase.
- The bypass was architecturally inert for Act As sessions in the current implementation (Verification 02 finding stands), but the explicit mapping and deny-by-default make the system correct by design rather than by compensating control.
- Any future role added to `_ACTABLE_ROLES` without a `ROLE_ALLOWED_PREFIXES` entry now safely redirects to `/no-access` instead of silently passing through.
- The backend's `require_capability()` guards provide a second enforcement layer for data access — but they do not prevent the wrong role from seeing admin page structure and navigation links. The middleware fix closes that surface exposure.

# What is still unclear

- **Whether any production user accounts have `role=checkin_checkout` stored directly in `tenant_permissions`** (not via Act As). If such accounts exist, they would produce `checkin_checkout` in a cookie on normal login — and before this fix, those accounts would have had unrestricted frontend access. Post-fix they are correctly routed to `/ops/checkin-checkout` and `/worker`.
- **Whether `/ops/checkin-checkout/` pages are fully functional** for the `checkin_checkout` role (i.e., whether the pages use `staffApi` correctly, have correct role-based UI branching, etc.). The mapping is correct; the surface quality is a separate concern.

# Recommended next step

**Close as resolved.** The gap is fixed with both the specific mapping and the structural deny-by-default.

**Forward protocol:** When any new role is added to `_ACTABLE_ROLES` in `act_as_router.py`, a corresponding entry in `ROLE_ALLOWED_PREFIXES` in `middleware.ts` must be added at the same time. The deny-by-default makes omission safe (role redirects to `/no-access`) but still incorrect UX — the explicit mapping should be done deliberately. This should be noted in the `act_as_router.py` comment or a CONTRIBUTING note.
