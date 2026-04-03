# Claim

`ops` is a broader operational role surface than any single worker role.

# Verdict

PROVEN

# Why this verdict

The `ops` role's allowed route prefix list in `middleware.ts` is the longest of any non-admin role: 6 distinct path prefixes covering operational, financial, task, and guest surfaces. Every other named worker role (cleaner, checkin, checkout, maintenance) is restricted to 2 paths or fewer. Even the `worker` role — which is the most permissive single-worker role — has 5 paths, all of which are operational/workflow paths. The `ops` role uniquely overlaps with both worker-facing and admin-facing data surfaces.

# Direct repository evidence

- `ihouse-ui/middleware.ts` lines 59–67 — `ROLE_ALLOWED_PREFIXES` mapping (authoritative access matrix)
- `ihouse-ui/middleware.ts` lines 70–71 — `FULL_ACCESS_ROLES` (admin and manager are unrestricted, not listed)
- `src/api/operations_router.py` — ops-specific backend endpoints
- `ihouse-ui/app/(app)/ops/page.tsx` — ops landing page

# Evidence details

**Authoritative route prefix matrix from `middleware.ts`:**

```typescript
const ROLE_ALLOWED_PREFIXES: Record<string, string[]> = {
    owner:         ['/owner', '/dashboard'],                                          // 2 prefixes
    worker:        ['/worker', '/ops', '/maintenance', '/checkin', '/checkout'],      // 5 prefixes
    cleaner:       ['/worker', '/ops'],                                               // 2 prefixes (Phase 831 restriction)
    ops:           ['/ops', '/dashboard', '/bookings', '/tasks', '/calendar', '/guests'], // 6 prefixes
    checkin:       ['/checkin', '/ops/checkin'],                                      // 2 prefixes
    checkout:      ['/checkout', '/ops/checkout'],                                    // 2 prefixes
    maintenance:   ['/maintenance', '/worker'],                                       // 2 prefixes
    identity_only: ['/welcome', '/profile', '/get-started', '/my-properties'],       // 4 prefixes (onboarding only)
};
```

**Comparative analysis:**

| Role | Path count | Surfaces accessible |
|------|-----------|---------------------|
| ops | 6 | ops, dashboard, bookings, tasks, calendar, guests |
| worker | 5 | worker, ops, maintenance, checkin, checkout |
| identity_only | 4 | welcome, profile, get-started, my-properties (onboarding only, no ops) |
| owner | 2 | owner, dashboard |
| cleaner | 2 | worker, ops |
| checkin | 2 | checkin, ops/checkin |
| checkout | 2 | checkout, ops/checkout |
| maintenance | 2 | maintenance, worker |

`ops` accesses 6 route prefixes. The next largest is `worker` at 5 — but those 5 paths are all workflow-facing (worker dashboard, ops hub, maintenance, checkin, checkout). The `ops` role's 6 paths span distinctly broader territory: `/dashboard` (management-level view), `/bookings` (reservation data), `/tasks` (full task board), `/calendar` (property calendar), `/guests` (guest data). These are surfaces that no single worker role can access.

**Unique `ops` surfaces not accessible to any single worker role:**
- `/bookings` — reservation data: not accessible to cleaner, checkin, checkout, maintenance, or worker
- `/calendar` — property calendar: not accessible to any single worker role
- `/guests` — guest data: not accessible to any single worker role
- `/tasks` — task board: not accessible to cleaner, checkin, checkout, or maintenance

**`ops` vs `worker` comparison:**
`worker` has access to `/maintenance` and `/checkin` and `/checkout` — which `ops` does NOT. `ops` has access to `/bookings`, `/calendar`, and `/guests` — which `worker` does NOT. These are complementary surfaces, not one a superset of the other.

**`ops` vs admin/manager:**
Admin and manager have unrestricted access (listed in `FULL_ACCESS_ROLES`, not in `ROLE_ALLOWED_PREFIXES`). `ops` is the most permissive NAMED restricted role, but it is still strictly less than admin or manager.

**Backend correlation — `operations_router.py`:**
The operations router exists in `src/api/operations_router.py` and is mounted in `main.py`. It provides multi-property, cross-functional query capabilities — consistent with the frontend route surface being broad. The ops role appears designed for a property operations coordinator or senior ops staff member, not a field worker.

# Conflicts or contradictions

- The name "ops" could be confused with `worker` by readers who assume "operations" means field workers. The `ops` role is closer to a read-heavy administrative or coordination role than a hands-on worker role. A cleaner is a worker who does ops work, but does NOT have the `ops` role — Phase 831 explicitly restricted cleaners to `['/worker', '/ops']` and removed broader access.
- `ops` lacks access to `/checkin`, `/checkout`, and `/maintenance` — paths that `worker` has. This means an `ops`-role user cannot directly perform the mobile check-in or check-out flows. The `ops` role appears designed for coordination and oversight, not field execution.
- `dashboard` is accessible to both `ops` and `owner`. These are likely different views of the same route (`/dashboard`) — but the exact filtering logic (if any) is not confirmed from middleware alone.

# What is still missing

- The exact `ops` role population: whether there are real users with `role="ops"` in any tenant, or whether this role is primarily used for Act As / Preview sessions to simulate ops-level access.
- Whether the `/bookings`, `/calendar`, `/guests` pages served to `ops`-role users show the same data as admin/manager views, or whether there is a secondary filter in those pages' data fetching logic.
- Whether `ops` can write (create/modify bookings, tasks) or is effectively read-only on those extended surfaces. The middleware grants route access but does not restrict to GET-only within those routes.

# Risk if misunderstood

If `ops` is treated as just another worker role (like `cleaner` or `checkin`), its broader route access — bookings, guests, calendar — will be overlooked when building role-specific data gates. A developer who adds a sensitive `/guests` or `/bookings` API endpoint and guards it with "accessible to workers but not guests" logic may inadvertently over-expose it to `ops`-role users who were not the intended audience.

Conversely, if `ops` is confused with admin/manager (because it can see `dashboard` and `bookings`), someone might assume `ops`-role users can reach admin-only surfaces like `/admin/*` — they cannot. `ops` is a mid-tier coordination role, broader than field workers but strictly less than management.
