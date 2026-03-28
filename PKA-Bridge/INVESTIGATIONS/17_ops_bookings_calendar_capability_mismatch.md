# Title

ops Role Can Navigate to /bookings and /calendar But Gets 403 From Every Booking API Endpoint — Middleware and Capability Guard Disagree

# Why this matters

The `ops` role was designed as an Operational Manager — a coordination role above workers, with read-access to data needed to manage operations. The middleware explicitly grants `ops` access to `/bookings` and `/calendar`. But the backend capability guard rejects `ops` for every booking endpoint with HTTP 403. The two controls were built at different phases and have never been reconciled. The result is a broken surface: ops users can navigate to these pages but cannot load any data. Any new feature built for ops on these surfaces will silently fail at the data layer until the mismatch is resolved.

# Original claim

`ops` is listed in `middleware.ts` `ROLE_ALLOWED_PREFIXES` with `/bookings` and `/calendar` allowed, but `require_capability("bookings")` in `capability_guard.py` has a hard-coded binary: admin (always allowed) or manager (DB capability check). All other roles — including `ops` — are denied at line 105 with HTTP 403 before reaching any capability check.

# Final verdict

PROVEN

# Executive summary

The mismatch is confirmed by direct reading of both files. `middleware.ts` line 63 explicitly names `/bookings` and `/calendar` in the `ops` allowed prefixes. `capability_guard.py` lines 100–113 have a binary role check: `admin` passes unconditionally; non-`manager` raises HTTP 403. `ops` is not `admin` and is not `manager`, so it hits the 403 branch every time. All booking read and write endpoints in `bookings_router.py`, `manual_booking_router.py`, and `booking_lifecycle_router.py` use `require_capability("bookings")`. The `ops` role cannot read or write any booking data through the normal API path.

This is not a security gap — the capability guard correctly blocks `ops` from booking data. It is a product coherence gap: the frontend says `ops` belongs on these pages; the backend says `ops` does not. The practical effect is broken pages.

# Exact repository evidence

- `ihouse-ui/middleware.ts` line 63 — `ops: ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests']`
- `src/api/capability_guard.py` lines 100–113 — admin allow; non-manager 403
- `src/api/bookings_router.py` lines 81, 212, 404, 508 — all endpoints: `Depends(require_capability("bookings"))`
- `src/api/manual_booking_router.py` lines 55, 320, 426 — same guard on create/cancel/amend
- `src/api/booking_lifecycle_router.py` line 218 — same guard on lifecycle visualization
- `ihouse-ui/app/(app)/bookings/page.tsx` header comment — "Manager / Admin — NOT cleaners, NOT workers"

# Detailed evidence

**The middleware grant (Phase 397):**
```typescript
// middleware.ts line 59–64
const ROLE_ALLOWED_PREFIXES: Record<string, string[]> = {
    owner:         ['/owner', '/dashboard'],
    worker:        ['/worker', '/ops', '/maintenance', '/checkin', '/checkout'],
    cleaner:       ['/worker', '/ops'],
    ops:           ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests'],
    checkin:       ['/checkin', '/ops/checkin'],
    checkout:      ['/checkout', '/ops/checkout'],
    maintenance:   ['/maintenance', '/worker'],
```
`/bookings` and `/calendar` are explicitly in the `ops` list. This was written at Phase 397 — it was a deliberate addition, not a copy-paste.

**The capability guard block (Phase 862 P37):**
```python
# capability_guard.py lines 100–113
if role == "admin":
    return None                         # ← admin: unconditional pass

if role != "manager":
    logger.warning(                     # ← ops lands here
        "capability_guard: role=%s denied for capability=%s user=%s",
        role, capability, user_id,
    )
    raise HTTPException(
        status_code=403,
        detail=f"CAPABILITY_DENIED: role '{role}' does not have '{capability}' capability.",
    )
# ... DB check for manager only follows
```
`ops` is not `"admin"` and is not `"manager"`. It hits the `role != "manager"` branch and gets HTTP 403. The guard was written to be a binary: "all capabilities are admin-or-delegated-manager only." The `ops` role was not in scope when the guard was designed.

**Coverage of the guard across booking endpoints:**
Every endpoint in the booking surface uses `require_capability("bookings")`:
- `GET /bookings` — list
- `GET /bookings/{id}` — single booking
- `GET /bookings/{id}/amendments` — amendment history
- `PATCH /bookings/{id}/status` — status update
- `POST /bookings/manual` — manual booking creation
- `DELETE /bookings/manual/{id}` — manual booking cancellation
- `PATCH /bookings/manual/{id}` — manual booking amendment
- `GET /admin/bookings/lifecycle-states` — lifecycle visualization

There is no ops-accessible booking endpoint. The middleware grant is entirely hollow.

**The bookings page predates the ops role entry:**
The bookings page header comment (`bookings/page.tsx`) was written at Phase 158 and explicitly scopes the page to Manager/Admin:
```typescript
// WHO creates bookings here:
//   - Manager / Admin — the primary user role
//   - NOT cleaners, NOT workers
```
`ops` is absent from this comment. The `ops` entry in `ROLE_ALLOWED_PREFIXES` was added at Phase 397 — 239 phases later. The page comment and the guard were never updated when `ops` was added to the middleware.

**The two controls' phase timeline:**
- Phase 158: `bookings/page.tsx` created — Manager/Admin only in comments
- Phase 397: middleware `ROLE_ALLOWED_PREFIXES["ops"]` includes `/bookings` and `/calendar`
- Phase 862 P37: `capability_guard.py` created — binary admin/manager logic, no ops path

The guard at Phase 862 post-dates the middleware grant at Phase 397 by 465 phases. The guard may have been intended to supersede the middleware grant, or it may simply not have been updated to account for the `ops` role.

**The calendar page (presumed behavior):**
The `/calendar` route is in the same allowed prefixes list as `/bookings`. The calendar frontend almost certainly calls booking endpoints to populate date-based views (the investigation of Issue 07 confirmed the calendar backend API is `GET /bookings`). If the calendar page makes any booking API call, it hits the same `require_capability("bookings")` guard and gets 403.

**Dev mode behavior:**
When `IHOUSE_DEV_MODE=true`, `require_capability` returns a no-op (`_noop`). In dev mode, ops users can access all booking data. This masks the mismatch during development — the breakage only manifests in production (or staging with dev mode off).

# Contradictions

- `ROLE_ALLOWED_PREFIXES["ops"]` in middleware includes `/bookings` — implying ops belongs on that surface
- `capability_guard.py` `require_capability("bookings")` denies `ops` — implying ops does not belong on that surface
- `bookings/page.tsx` comment names Manager/Admin only — consistent with the guard, inconsistent with the middleware
- The `ops` role is described as Operational Manager (above worker, below admin/manager) — an Operational Manager might need booking visibility to coordinate operations

# What is confirmed

- `middleware.ts` grants `ops` access to `/bookings` and `/calendar` at Phase 397
- `capability_guard.py` denies `ops` for `require_capability("bookings")` with a hard 403 at Phase 862 P37
- All booking endpoints use `require_capability("bookings")`
- `ops` cannot read or write any booking data through the API
- The bookings page header scopes to Manager/Admin — does not mention `ops`
- In dev mode the guard is bypassed and ops can access booking data (masking the mismatch)

# What is not confirmed

- Whether the Phase 397 middleware addition of `/bookings` to the ops surface was intentional (expecting the capability guard to be extended) or incidental (copied from another role's surface)
- Whether the Phase 862 P37 guard was designed to supersede the Phase 397 middleware grant
- Whether any `ops` user in any tenant has ever been granted the `bookings` capability through `tenant_permissions` delegation by an admin (which would resolve the mismatch for that specific user without a code change)
- Whether the `/calendar` frontend page calls any non-booking endpoint that would work for `ops` (e.g., a separate calendar API with different authorization)

# Practical interpretation

**For an ops user in production:**
1. Login → role = "ops"
2. Navigate to `/bookings` → middleware passes (ops is in the allowed list)
3. Page loads → immediately calls `GET /bookings` → `require_capability("bookings")` → HTTP 403
4. Page shows error state or empty booking list
5. Navigate to `/calendar` → same path, same 403
6. Both pages are visually accessible but functionally broken

**Two resolution paths, both valid:**

**Path A — Remove `/bookings` and `/calendar` from the ops middleware allowlist:**
If ops does not need booking data (the `/tasks` board provides sufficient operational context), remove these two prefixes from `ROLE_ALLOWED_PREFIXES["ops"]`. Ops users attempting to navigate to `/bookings` would be redirected to `/no-access`. Consistent with the bookings page comment (Manager/Admin only).

**Path B — Add `ops` to the `require_capability("bookings")` allowed roles:**
If ops should genuinely see booking data for coordination purposes, extend the capability guard to allow `ops` unconditionally (similar to `admin`) or with a separate ops-specific DB check. This would require changing line 105 of `capability_guard.py` from `if role != "manager":` to a more nuanced check. Consistent with the middleware grant at Phase 397.

Both paths require a product decision: does an Operational Manager need booking visibility? Neither the middleware nor the guard can answer this — they were written by different phases with different assumptions.

# Risk if misunderstood

**If the broken pages are assumed to mean ops shouldn't navigate there:** The middleware grant is still in place. Ops can still navigate to the pages. The 403 is not a redirect — it's a data fetch failure on a loaded page. Users see errors, not access-denied.

**If the dev mode bypass is assumed to mean the feature works:** In dev mode, `require_capability` is a no-op and ops can access bookings freely. This masks the production behavior. Ops-facing booking features tested in dev will silently break in production.

**If a new ops-facing feature is added to `/bookings`:** It will work in dev and fail silently in production on every data call. The developer will need to know about this mismatch to debug the 403.

# Recommended follow-up check

1. **Make the product decision**: Should ops see booking data? Answer determines which path to take.
2. **If Path A** (remove from middleware): change `middleware.ts` line 63 to remove `/bookings` and `/calendar` from ops prefixes. Update the ops role documentation.
3. **If Path B** (extend the guard): change `capability_guard.py` to add `ops` as a third allowed-unconditionally role alongside `admin`, OR add a separate ops-level booking capability check. Also update `bookings/page.tsx` header comment to include `ops` in the intended audience.
4. **Verify the calendar page API call**: Read `ihouse-ui/app/(app)/calendar/page.tsx` to confirm it calls booking endpoints. If it calls a different backend (e.g., a dedicated calendar endpoint with only `jwt_auth`), the calendar mismatch may be separable from the bookings mismatch.
