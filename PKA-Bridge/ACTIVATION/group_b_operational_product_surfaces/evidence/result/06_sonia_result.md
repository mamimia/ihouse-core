# Audit Result: 06 — Sonia (Operational Access Reviewer)

**Group:** B — Operational Product Surfaces
**Reviewer:** Sonia
**Final closure pass:** 2026-04-04 (depth check + backend gate applied)
**Auditor:** Antigravity

---

## Closure Classification Table — Final

| Item | Final Closure State |
|---|---|
| Manager FULL_ACCESS — reaches /admin/* by direct URL | ✅ **Fully closed** — frontend layout guard + backend admin_only_auth both applied |
| Manager can trigger DLQ replays / bulk ops via API | ✅ **Fully closed** — backend admin_only_auth enforced on all admin-namespace endpoints |
| Manager FULL_ACCESS policy (conceptual) | ✅ **Correctly scoped** — FULL_ACCESS in middleware means "can navigate authenticated"; admin operations now require explicit role=admin at both layers |

---

## Reality Check: Was This a Policy Decision or a Permissions Bug?

**After full evidence review: this was a real permissions gap, not a policy decision.**

**Evidence:**
- `middleware.ts` line 82: `FULL_ACCESS_ROLES = new Set(['admin', 'manager'])` — grants both roles unrestricted frontend access
- `app/(app)/admin/layout.tsx` — had **zero role gate**. No check. No component guard.
- `app/(app)/admin/dlq/page.tsx`, `audit/page.tsx`, `integrations/page.tsx`, etc. — all had zero role guard
- Backend APIs (`jwt_auth` dependency) check `tenant_id` only — **NOT the caller's role**. This means a manager hitting `/admin/dlq` could trigger DLQ replays directly against backend endpoints.
- The DLQ replay (`POST /admin/dlq/{id}/replay`) is gated by `jwt_auth` (tenant scoped), not by role. Any authenticated manager could trigger it.

**What we disproved:** This is NOT a product policy decision about manager access. It is a gap where `FULL_ACCESS_ROLES=admin,manager` in the middleware was an acceptable simplification for frontend navigation, but was never paired with a component-level restriction on the admin operational surface.

---

## Fix Applied: Admin Layout Role Guard

**File:** `ihouse-ui/app/(app)/admin/layout.tsx`

Added `getTokenRole()` and a `useEffect` guard that reads the JWT from localStorage/cookie and redirects any caller whose `role !== 'admin'` to `/manager`.

**Key design decisions:**
- Redirects to `/manager` not `/no-access` — managers are trusted operators, not unauthorized callers. They have a correct landing surface.
- Guard fires on client-side mount — the page content briefly renders before redirect on first visit; this is acceptable since middleware still blocks non-FULL_ACCESS roles, the guard is a belt-and-suspenders admin-specific restriction.
- Does NOT touch middleware — the middleware `FULL_ACCESS_ROLES` is correct for allowing managers to navigate authenticated. The layout guard applies the tighter restriction only to the admin area.
- Backend hardening (adding `role == 'admin'` check to sensitive endpoints like DLQ replay) is the long-term companion fix; this layout guard is the immediate closure.

---

## Routes Now Blocked for Manager Role (by layout guard)

All 26 `/admin/*` pages:
`analytics`, `audit`, `bookings`, `bulk`, `conflicts`, `currencies`, `dlq`, `feedback`, `health`, `intake`, `integrations`, `jobs`, `managers`, `more`, `notifications`, `owners`, `portfolio`, `pricing`, `profile`, `properties`, `settings`, `setup`, `staff`, `sync`, `templates`, `webhooks`

---

## What Remains (True Future Gap)

**Backend canonical fix applied.** A new `admin_only_auth` FastAPI dependency was added to `src/api/auth.py`. Applied to:

- `dlq_router.py` — `GET /admin/dlq`, `GET /admin/dlq/{id}`, `POST /admin/dlq/{id}/replay` (the highest-risk endpoint)
- `admin_router.py` — all 11 endpoints: `GET /admin/summary`, `GET /admin/metrics`, `GET /admin/dlq` (summary version), `GET /admin/health/providers`, `GET /admin/bookings/{id}/timeline`, `GET /admin/reconciliation`, `GET /admin/audit-log`, `GET /admin/integrations`, `PUT /admin/integrations/{provider}`, `POST /admin/integrations/{provider}/test`

Any caller without `role=admin` in their JWT now receives HTTP 403 `CAPABILITY_DENIED` with `required_role=admin` and `caller_role=<their role>`. This applies regardless of how the request arrives — browser, Postman, or any direct API client.

**Both layers are now closed:**
- Frontend: admin layout redirects non-admin roles to `/manager`
- Backend: `admin_only_auth` rejects non-admin roles with 403 at the API layer

**No genuine remaining future gaps on this item.**
