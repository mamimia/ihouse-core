# Evidence File: Daniel — Role & Permission Architect

**Paired memo:** `03_daniel_role_permission_architect.md`
**Evidence status:** Most claims directly proven by code reading; capability enforcement pattern now confirmed

---

## Claim 1: 9 canonical roles in canonical_roles.py as single source of truth

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/services/canonical_roles.py`
- CANONICAL_ROLES frozenset: admin, manager, ops, owner, worker, cleaner, checkin, checkout, maintenance
- FULL_ACCESS_ROLES: {admin, manager}
- STAFF_ROLES: {worker, cleaner, checkin, checkout, maintenance, ops}
- INVITABLE_ROLES: CANONICAL_ROLES - {admin}
- IDENTITY_ONLY = "identity_only" (Phase 862 P28)

**What was observed:** Exactly 9 roles in the canonical set, plus identity_only as a system state. Classifications are clean and immutable (frozenset).

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 2: Deny-by-default at frontend edge middleware

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/middleware.ts`
- `ROLE_ALLOWED_PREFIXES` maps: owner→[/owner, /dashboard], worker→[/worker, /ops, /maintenance, /checkin, /checkout], cleaner→[/worker, /ops], ops→[/ops, /dashboard, /bookings, /tasks, /calendar, /guests], checkin→[/checkin, /ops/checkin], checkout→[/checkout, /ops/checkout], checkin_checkout→[/ops/checkin-checkout, /worker], maintenance→[/maintenance, /worker], identity_only→[/welcome, /profile, /get-started, /my-properties]
- admin/manager: unrestricted (full access)
- Empty role → redirect to /no-access
- Unmapped roles → redirect to /no-access

**What was observed:** The middleware decodes JWT at edge, checks role against explicit prefix allowlist. Anything not explicitly allowed is denied. This is deny-by-default.

**Confidence:** HIGH

**Uncertainty:** JWT is decoded at edge WITHOUT signature verification (Base64url decode only). Signature verification happens later in `verify_jwt()` on the backend. This means the role claim at edge is trusted from the token payload without cryptographic verification. The risk is low (tokens are issued by the system) but it is a trust assumption.

---

## Claim 3: Route access vs API enforcement gap — manager can reach /financial but may be denied by API

**Status:** DIRECTLY PROVEN with mechanism identified

**Evidence basis:**
- File: `ihouse-ui/middleware.ts` — manager has FULL_ACCESS (unrestricted route access)
- File: `src/api/capability_guard.py` — `require_capability("financial")` function
- File: `src/api/financial_router.py` — all 4 endpoints use `Depends(require_capability("financial"))`
- File: `src/api/financial_writer_router.py` — both endpoints use `Depends(require_capability("financial"))`

**What was observed:** Manager with full route access reaches `/financial` page. The page calls API endpoints. Each endpoint has `require_capability("financial")`. If the manager lacks `financial` delegation in `tenant_permissions.permissions`, the API returns HTTP 403 with code `CAPABILITY_DENIED`. Frontend api.ts does NOT logout on 403 — the user sees an error state.

**Confidence:** HIGH. The gap is architecturally real and the mechanism is clear.

**Uncertainty:** What exactly does the frontend show? A blank page? An error component? An AccessDenied message? This is Talia's domain (interaction architecture).

---

## Claim 4: Unknown role fallback behavior

**Status:** DIRECTLY PROVEN — two layers with different behavior

**Evidence basis:**
- File: `ihouse-ui/middleware.ts` — empty role → /no-access. Roles not in ROLE_ALLOWED_PREFIXES and not admin/manager → /no-access
- File: `ihouse-ui/lib/roleRoute.ts` — unknown role → `/dashboard` (default fallback)

**What was observed:** Two different fallback behaviors:
1. middleware.ts: If role is unknown, user is redirected to /no-access (deny)
2. roleRoute.ts: If role is unknown, user is routed to /dashboard (allow)

But middleware.ts runs FIRST (edge level). If an unknown role tries to access /dashboard, middleware checks ROLE_ALLOWED_PREFIXES — unknown role is not in the map, so middleware redirects to /no-access. roleRoute.ts's fallback to /dashboard is unreachable for unknown roles because middleware blocks the route.

**Net effect:** Unknown roles are effectively denied. roleRoute.ts fallback is dead code for unknown roles.

**Confidence:** HIGH

**Uncertainty:** None for the current flow. The roleRoute.ts fallback could become reachable if middleware is modified to be more permissive.

---

## Claim 5: Settlement and financial endpoints may lack role guards

**Status:** REVISED — financial endpoints have capability guards; settlement endpoints use jwt_identity but no capability guard

**Evidence basis:**
- File: `src/api/financial_router.py` — `Depends(require_capability("financial"))` on all 4 endpoints
- File: `src/api/financial_writer_router.py` — `Depends(require_capability("financial"))` on both endpoints
- File: `src/api/checkout_settlement_router.py` — uses `Depends(jwt_identity)` for authentication, but NO `require_capability()` call observed
- File: `src/api/checkin_settlement_router.py` — uses `Depends(jwt_identity)` for authentication
- File: `src/api/booking_checkin_router.py`, line 468: `_assert_checkout_role(identity, db)` — explicit role guard on checkout

**What was observed:**
- Financial endpoints: PROPERLY GUARDED with capability checks ✓
- Checkout booking endpoint: PROPERLY GUARDED with role assertion ✓
- Settlement endpoints (meter reading, draft, calculate, finalize): AUTHENTICATED via jwt_identity but NO explicit role or capability guard observed
- This means any authenticated user with a valid JWT could potentially call settlement mutation endpoints

**Confidence:** HIGH for financial guards. MEDIUM for settlement gap — the settlement router header states invariants but role guard absence needs confirmation by reading the full endpoint signatures.

**Uncertainty:** The settlement router may have role checks embedded in the function body rather than as Depends() decorators. Need to read the full endpoint functions.

**Follow-up check:** Read the complete endpoint signatures of checkout_settlement_router's mutation endpoints (start_settlement, calculate, finalize) to confirm presence or absence of role guards.

---

## Claim 6: Dev mode bypass risk

**Status:** DIRECTLY PROVEN with mitigation confirmed

**Evidence basis:**
- File: `src/api/auth.py` — `IHOUSE_DEV_MODE=true` returns "dev-tenant" without JWT verification
- File: `src/api/capability_guard.py` — dev mode returns no-op guard (no DB lookup)
- Production block: `env_validator.py` raises fatal error if `IHOUSE_DEV_MODE=true` with `IHOUSE_ENV=production`

**What was observed:** Dev mode bypass exists and is intentional. Production mitigation (env_validator) prevents it from being active in production. The risk is contained.

**Confidence:** HIGH

**Uncertainty:** If env_validator fails to load (import error, missing file), dev mode could leak to production. This is a defense-in-depth concern, not an active risk.

---

## Claim 7: 414 auth dependencies across 120 routers

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- Grep across `src/api/` for `Depends(jwt_identity)` and `Depends(jwt_auth)`: 414 occurrences across 120 files

**What was observed:** Authentication is pervasively enforced. 120 out of 134 routers have auth dependencies. The remaining 14 are likely public endpoints (guest portal, invite acceptance, health checks).

**Confidence:** HIGH

**Uncertainty:** Which 14 routers lack auth? These should be exclusively public endpoints.

**Follow-up check:** Identify the ~14 routers without jwt_auth/jwt_identity to confirm they are all intentionally public.
