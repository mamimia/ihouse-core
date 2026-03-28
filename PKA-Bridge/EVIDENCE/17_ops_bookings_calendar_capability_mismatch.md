# Claim

The `ops` role is granted access to `/bookings` and `/calendar` in `middleware.ts` (`ROLE_ALLOWED_PREFIXES["ops"]`), but `require_capability("bookings")` in `bookings_router.py` denies all roles except `admin` and capability-delegated `manager`. These two access controls disagree on whether `ops` should see booking data.

# Verdict

PROVEN

# Why this verdict

Direct reading of both files confirms the mismatch:
- `middleware.ts` line 63: `ops: ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests']` — ops explicitly granted `/bookings` and `/calendar`
- `capability_guard.py` lines 100–113: `require_capability()` allows `admin` unconditionally; checks DB delegation for `manager`; raises HTTP 403 for all other roles
- The guard's hard-coded rejection of non-manager, non-admin roles means `ops` always gets 403 from any bookings endpoint — the guard has no path for `ops` to pass

The two controls were written at different phases (middleware at Phase 397; capability guard at Phase 862 P37) and have never been reconciled.

# Direct repository evidence

- `ihouse-ui/middleware.ts` line 63 — `ops` allowed prefixes include `/bookings` and `/calendar`
- `src/api/capability_guard.py` lines 100–113 — guard logic: admin → allow; non-manager → 403
- `src/api/bookings_router.py` line 81, 212, 404, 508 — all read/write endpoints use `require_capability("bookings")`
- `ihouse-ui/app/(app)/bookings/page.tsx` header comment — "Filterable booking list for operations managers. WHO creates bookings here: Manager / Admin — NOT cleaners, NOT workers"
- `src/api/capability_guard.py` lines 61–87 — dev mode bypass (IHOUSE_DEV_MODE=true disables the guard entirely)

# Evidence details

**Middleware grants access — ops can navigate to the pages:**
```typescript
// middleware.ts line 63
ops: ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests'],
```
An `ops` user who navigates to `/bookings` or `/calendar` passes the middleware check without redirect.

**Capability guard denies data — ops gets 403 on every API call:**
```python
# capability_guard.py lines 100–113
if role == "admin":
    return None          # allowed unconditionally

if role != "manager":
    logger.warning("capability_guard: role=%s denied...", role, ...)
    raise HTTPException(status_code=403, ...)  # ← ops hits this
```
The guard has two exit paths: allow (admin) and DB-check (manager). Every other role — including `ops` — is denied at line 105 before reaching the DB check. There is no `ops`-specific path.

**All bookings endpoints are guarded:**
```python
# bookings_router.py — every endpoint:
_cap: None = Depends(require_capability("bookings")),
```
This covers GET /bookings, GET /bookings/{id}, GET /bookings/{id}/amendments, PATCH /bookings/{id}/status, and all equivalent endpoints in `manual_booking_router.py` and `booking_lifecycle_router.py`.

**The bookings page header comment contradicts ops access:**
```typescript
// bookings/page.tsx header
// WHO creates bookings here:
//   - Manager / Admin — the primary user role
//   - NOT cleaners, NOT workers
```
The comment names Manager/Admin only. `ops` is not mentioned. This was written at Phase 158 — before the `ops` role was formally added to `ROLE_ALLOWED_PREFIXES` at Phase 397. Neither was updated when the other changed.

**When did each control last address `ops`?**
- Middleware `ROLE_ALLOWED_PREFIXES["ops"]` — Phase 397 (explicitly includes `/bookings`)
- `capability_guard.py` logic — Phase 862 P37 (no mention of `ops`; admin/manager binary)
- These phases never overlap in the file histories

# Conflicts or contradictions

- Middleware says ops can see `/bookings` and `/calendar`. Capability guard says ops cannot read booking data. The user experience is a navigable but empty/erroring page — or a silent 403 in the network tab.
- The bookings page comment explicitly lists Manager/Admin as the intended users and excludes workers. `ops` is neither mentioned in favor nor excluded — it is simply absent from both the comment and the guard's allow list.
- The `ROLE_ALLOWED_PREFIXES` comment at the top of `middleware.ts` says `ops → /ops, /dashboard, /bookings, /tasks, /calendar` — the comment is accurate to the code. But the comment was never reconciled with the capability guard.

# What is still missing

- Whether the `/calendar` frontend page calls any endpoint other than the bookings API (i.e., whether it calls a dedicated calendar endpoint that might have different capability requirements)
- Whether `ops` users have ever been delegated the `bookings` capability through `tenant_permissions` by an admin — which would make the mismatch a non-issue in practice for those tenants
- Whether the middleware `ops` entry for `/bookings` was intentional (ops should see bookings, the capability guard needs updating) or accidental (ops should not see bookings, the middleware entry needs trimming)

# Risk if misunderstood

**If the middleware grant is assumed to mean ops can access booking data:** Any ops user navigating to `/bookings` sees an error or empty state. This is a broken UX, not a security gap.

**If the capability guard is assumed to fully protect booking data:** It does — `ops` cannot read booking data via the API regardless of what the middleware allows. The security boundary holds. Only admin and capability-delegated manager can reach booking data.

**If this is left unresolved:** Every `ops` user has a navigable but broken `/bookings` and `/calendar` surface. Future developers adding ops-facing features to these pages will get silent 403s and may not immediately identify the capability guard as the cause.
