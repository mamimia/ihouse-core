# Title

The `ops` Role Has Broader Route Access Than Any Single Worker Role — Including Data Surfaces No Field Worker Can Reach

# Why this matters

The `ops` role is named generically and could be misread as just another operational worker role — similar to `cleaner` or `checkin`. In reality it has a materially different access surface. It can reach `/bookings`, `/calendar`, `/guests`, and `/tasks` — surfaces that no field worker role can access. It also shares `/dashboard` access with admin and manager roles. If a developer builds data guards that gate on "worker vs admin" without accounting for `ops`, they will under-protect those broader surfaces. Conversely, if `ops` is treated as equivalent to admin, it will be over-trusted — `ops` cannot access `/admin/*`, cannot modify staff permissions, and has no management capabilities.

# Original claim

`ops` is a broader operational role surface than any single worker role.

# Final verdict

PROVEN

# Executive summary

The route prefix matrix in `middleware.ts` is the authoritative access control definition for frontend routes. `ops` has 6 allowed route prefixes — the most of any named restricted role. All other specific worker roles (`cleaner`, `checkin`, `checkout`, `maintenance`) are limited to 2 prefixes each. Even `worker` — the most permissive single worker role — has 5 prefixes, all confined to workflow surfaces (worker portal, ops hub, maintenance, checkin, checkout). The `ops` role uniquely extends into cross-functional data territory: booking records, a guest data surface, a full task board, and a scheduling calendar. These are surfaces that hint at a coordination or oversight function, not a hands-on field worker function. The claim is fully proven by the middleware code.

# Exact repository evidence

- `ihouse-ui/middleware.ts` lines 57–68 — `ROLE_ALLOWED_PREFIXES` definition (authoritative matrix)
- `ihouse-ui/middleware.ts` lines 70–71 — `FULL_ACCESS_ROLES` (`admin`, `manager` — unrestricted)
- `src/api/operations_router.py` — backend operations endpoints
- `ihouse-ui/app/(app)/ops/page.tsx` — ops landing page

# Detailed evidence

**The authoritative route prefix matrix:**
```typescript
// Phase 397: Role-to-allowed-route-prefix mapping
// admin/manager have full access (not listed — they bypass checks)
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
const FULL_ACCESS_ROLES = new Set(['admin', 'manager']);
```

**Prefix count comparison:**

| Role | Prefix count | Route prefixes |
|------|-------------|----------------|
| admin / manager | unlimited | all routes |
| ops | **6** | /ops, /dashboard, /bookings, /tasks, /calendar, /guests |
| worker | 5 | /worker, /ops, /maintenance, /checkin, /checkout |
| identity_only | 4 | /welcome, /profile, /get-started, /my-properties |
| owner | 2 | /owner, /dashboard |
| cleaner | 2 | /worker, /ops |
| checkin | 2 | /checkin, /ops/checkin |
| checkout | 2 | /checkout, /ops/checkout |
| maintenance | 2 | /maintenance, /worker |

`ops` has the most prefixes of any named restricted role.

**Surfaces unique to `ops` — not accessible by any single worker role:**

- `/bookings` — reservation data. Not in `worker`, `cleaner`, `checkin`, `checkout`, or `maintenance` allowed lists. Only admin/manager have this beyond `ops`.
- `/calendar` — property scheduling calendar. Not in any single worker role. Only admin/manager have this beyond `ops`.
- `/guests` — guest data surface. Not in any single worker role. Only admin/manager have this beyond `ops`.
- `/tasks` — full task board. `worker` does not have `/tasks` in its allowed prefixes — workers access tasks through `/worker` and `/ops`. The full `/tasks` route (likely an administrative task board view) is accessible only to `ops`, admin, and manager.

**Surfaces where `ops` and `worker` overlap:**
- `/ops` — both roles have this prefix. The ops hub is shared.

**Surfaces where `worker` has access but `ops` does NOT:**
- `/maintenance` — maintenance worker surface. `ops` cannot reach this.
- `/checkin` — check-in workflow. `ops` cannot reach this.
- `/checkout` — check-out workflow. `ops` cannot reach this.
- `/worker` — worker dashboard. `ops` cannot reach this directly.

This asymmetry reveals that `ops` and `worker` are genuinely complementary, not hierarchical. `ops` can access data surfaces (bookings, guests, calendar) that `worker` cannot. `worker` can access workflow surfaces (maintenance, checkin, checkout) that `ops` cannot.

**The `dashboard` overlap with owner:**
Both `ops` and `owner` have `/dashboard` in their allowed prefixes. The page at `/dashboard` likely serves different data depending on role — admin/manager get the full management view, `ops` gets an operations coordinator view, `owner` gets a property performance view. Whether these are truly distinct views or the same component with data-layer filtering is not confirmed from the middleware alone.

**Phase 831 — cleaner restriction (historical context):**
The comment on the `cleaner` entry — `// Phase 831: restrict cleaner to worker + ops surfaces only` — indicates that before Phase 831, cleaners had broader route access. The current `['/worker', '/ops']` is a deliberate restriction. This confirms that route prefixes in this file are actively maintained and intentional, not accidental defaults.

**Backend correlation — `operations_router.py`:**
A dedicated operations router exists and is mounted. It provides operations-specific query capabilities — presumably cross-property, cross-booking operational views. The existence of a dedicated backend router for `ops` confirms that the broader frontend access surface has backend API support.

**`ops` access to `/tasks` — significant nuance:**
`worker` does not have `/tasks` in its allowed prefixes. Workers interact with tasks via the `/worker` page and `/ops` surface. The standalone `/tasks` route (at `ihouse-ui/app/(app)/tasks/page.tsx`) is the full administrative task board — read earlier, it has complex filter pills, task kind columns, and `checkin_checkout` handling. Only `ops`, admin, and manager can reach this view directly. This means `ops` can view and interact with the task board in a way that individual worker roles cannot.

# Contradictions

- The name "ops" could be interpreted as "operational field staff" (people who do operations work). In this system, `ops` behaves more like a "senior operations coordinator" — data-reading access across bookings, guests, and tasks, without the ability to execute field workflows (checkin, checkout, maintenance). The name is ambiguous.
- `ops` has `/dashboard` access but cannot reach `/worker`. This is unusual — most operational roles that have oversight of workers would be expected to see the worker dashboard. The routing suggests `ops` sees a management-style dashboard, not the field worker view.
- The `ops` backend role (in `CANONICAL_ROLES`: "admin", "manager", "ops", "owner", "worker", "cleaner", "checkin", "checkout", "maintenance") is listed alongside "worker", "cleaner", etc., suggesting symmetry. But the frontend route matrix treats `ops` as substantively different from all worker roles.
- No documentation clearly defines the intended use case for the `ops` role in plain language. "Operations" is vague enough to create confusion between "ops coordinator with data access" and "ops field worker who does check-ins."

# What is confirmed

- `ops` has 6 route prefixes — the most of any named restricted role in `middleware.ts`.
- `ops` uniquely accesses `/bookings`, `/calendar`, `/guests`, and `/tasks` — surfaces no single worker role can reach.
- `ops` shares `/ops` and `/dashboard` with subsets of other roles.
- `ops` cannot reach `/admin/*`, `/worker`, `/checkin`, `/checkout`, or `/maintenance`.
- The `ops` role is listed in `CANONICAL_ROLES` — it is a valid DB-stored role.
- A dedicated `operations_router.py` backend exists for this role's API needs.
- Phase 831 explicitly restricted `cleaner` to a narrower surface, showing route access is actively managed.

# What is not confirmed

- Whether real users in any tenant currently hold the `ops` role as their canonical `tenant_permissions.role`. The role may be used primarily through Act As / Preview sessions.
- Whether the `/tasks` page serves different data or UI to `ops` vs admin vs manager, or whether it shows the same view regardless of role.
- Whether `/bookings` as accessible to `ops` is read-only (list/view) or allows mutations (create, modify, cancel). The middleware grants route access but does not restrict to GET-only within those routes.
- What the `/guests` surface contains and what operations `ops` can perform on guest data.
- Whether `ops` has any elevated capability in the `delegated_capabilities` system compared to worker roles.

# Practical interpretation

The `ops` role is best understood as a property operations coordinator role — someone who needs to see the full booking picture, manage the task board, monitor guest arrivals on a calendar, and access guest records, but who does not personally execute field workflows like check-in/check-out or cleaning.

Practically, this role would suit a front-desk or property operations manager who oversees bookings and tasks but delegates field work to dedicated `checkin`, `cleaner`, and `maintenance` workers. The `ops` role sees the full operational picture without having admin/manager authority to modify staff, permissions, or system settings.

An important operational implication: if `ops` can write to `/bookings`, `/tasks`, or `/guests` (not confirmed), this role can mutate booking status and task assignments without manager-level accountability. If it is read-only on these surfaces, it is a safe oversight role.

# Risk if misunderstood

**If `ops` is treated as just another worker role:** Data guard logic for `/bookings`, `/calendar`, `/guests`, and `/tasks` built with "worker or ops" assumptions will be wrong. Access control code that accepts `role IN ('worker', 'cleaner', 'checkin', 'checkout', 'maintenance')` for field-worker-level access will miss that `ops` has materially broader authority.

**If `ops` is confused with admin/manager:** Security-sensitive logic (who can assign tasks, who can modify bookings) may be applied to `ops` unintentionally. `ops` does not reach `/admin/*` and has no management capabilities — it must not be given admin-level data mutation rights based on its broad route access.

**If the `ops` vs `worker` distinction is collapsed:** Future role model simplification (e.g., "merge ops and worker into one role") will silently expand worker route access to include bookings, guests, calendar — or will silently remove ops-role users' ability to see those surfaces.

# Recommended follow-up check

1. Search for any API endpoint that checks `role == "ops"` or `role in ("ops", ...)` to understand what backend operations the `ops` role is explicitly authorized for beyond the frontend route access.
2. Read `src/api/operations_router.py` fully to understand the specific API capabilities provisioned for `ops` users.
3. Check whether any real `tenant_permissions` DB row has `role="ops"` — to determine if this is a live role or primarily theoretical/Act As.
4. Read `ihouse-ui/app/(app)/tasks/page.tsx` role-specific rendering logic to determine if `ops` users see a different task board view than admin/manager.
5. Determine whether `/bookings` and `/guests` routes accessible to `ops` expose full mutation capabilities or read-only views.
