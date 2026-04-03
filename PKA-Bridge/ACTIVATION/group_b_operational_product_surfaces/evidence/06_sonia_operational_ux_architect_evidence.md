# Evidence File: Sonia — Operational UX Architect

**Paired memo:** `06_sonia_operational_ux_architect.md`
**Evidence status:** Strong structural evidence from frontend codebase; visibility enforcement needs deeper trace

---

## Claim 1: 7 distinct role surfaces with structural boundaries

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/middleware.ts`, lines 67-79: ROLE_ALLOWED_PREFIXES map with explicit per-role prefix lists
- File: `ihouse-ui/lib/roleRoute.ts`, lines 32-45: ROLE_ROUTES map with per-role landing pages
- Files: `ihouse-ui/app/(app)/admin/` (37+ subdirs), `ihouse-ui/app/(app)/manager/` (8 pages), `ihouse-ui/app/(app)/owner/` (1 page), `ihouse-ui/app/(app)/ops/` (6 pages), `ihouse-ui/app/(app)/worker/` (1 page), `ihouse-ui/app/(app)/dashboard/` (1 page)

**What was observed:** Each role has a defined surface area. Admin has 37+ pages, manager has 8 pages in a dedicated cockpit, owner has a single portal, ops has a hub + 5 worker sub-role surfaces. The middleware deny-by-default pattern ensures roles cannot access each other's surfaces by URL manipulation (except admin and manager, which have FULL_ACCESS).

**Confidence:** HIGH

**Uncertainty:** The content depth of each surface (what data each page actually renders) was not traced. Directory structure proves the surfaces exist; it doesn't prove they're fully populated.

---

## Claim 2: Three-shell architecture (Sidebar, OMSidebar, MobileStaffShell)

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/AdaptiveShell.tsx`, lines 41-73: Role-specific shell detection and routing
- File: `ihouse-ui/components/MobileStaffShell.tsx`: Full-screen mobile shell with forced dark theme (line 186: `data-theme="dark"`)
- File: `ihouse-ui/components/OMSidebar.tsx`, lines 4-18: Dedicated operational manager sidebar
- File: `ihouse-ui/components/Sidebar.tsx`, lines 41-55: Standard sidebar with role-filtered NAV_ITEMS

**What was observed:** AdaptiveShell detects three contexts:
1. Mobile staff routes (`/worker`, `/ops/cleaner`, `/ops/checkin`, `/ops/checkout`, `/ops/maintenance`) → bypass sidebar → MobileStaffShell
2. Manager role (effective role === 'manager') → OMSidebar with dedicated OM_NAV
3. All other routes → standard Sidebar with role-filtered navigation items

MobileStaffShell forces dark theme at component level. OMSidebar is a completely separate component from Sidebar — not a filtered version.

**Confidence:** HIGH

**Uncertainty:** None. Three distinct shell implementations confirmed in code.

---

## Claim 3: Manager has FULL_ACCESS in middleware

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/middleware.ts`, line 82: `const FULL_ACCESS_ROLES = ['admin', 'manager']`

**What was observed:** Both admin and manager are in the FULL_ACCESS_ROLES array. Middleware skips prefix checking for these roles — they can access any route. The structural separation between admin and manager surfaces is navigational (OMSidebar doesn't link to admin pages) but not enforced at middleware level.

**Confidence:** HIGH

**Uncertainty:** Whether this is intentional (managers are trusted, may need ad-hoc admin page access) or an oversight. No documentation found explaining this design decision.

---

## Claim 4: 8 owner visibility flags with progressive trust defaults

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `src/api/owner_portal_v2_router.py`, lines 46-55: `_DEFAULT_VISIBILITY` dictionary
- File: `src/api/owner_portal_v2_router.py`, lines 58-94: PUT endpoint for setting visibility
- File: `src/api/owner_portal_v2_router.py`, lines 97-117: GET endpoint for retrieving visibility
- File: `src/api/owner_portal_v2_router.py`, lines 124-188: Filtered summary API

**What was observed:** 8 flags exist:
- Default ON: bookings, financial_summary, occupancy_rates
- Default OFF: maintenance_reports, guest_details, task_details, worker_info, cleaning_photos

Admin can toggle per owner per property. Summary API (lines 124-188) references visibility settings, but whether the query actually filters data based on flags (vs. returning everything and relying on frontend filtering) requires tracing the SQL/RPC call at that endpoint.

**Confidence:** HIGH on flag existence and toggle endpoints. MEDIUM on query-level enforcement.

**Uncertainty:** The summary endpoint was read at the route level but the actual Supabase query construction (whether it conditionally includes/excludes data based on visibility flags) was not traced to the SQL level. If filtering is frontend-only, it's a data leak.

**Follow-up check:** Read lines 124-188 of `owner_portal_v2_router.py` in detail to trace whether the SELECT query conditionally joins/excludes tables based on visibility flags.

---

## Claim 5: Role-specific bottom navigation for each worker sub-role

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/BottomNav.tsx`, lines 57-98: Five distinct bottom nav configs
  - CHECKIN_BOTTOM_NAV: [Home, Check-in, Tasks]
  - CHECKOUT_BOTTOM_NAV: [Home, Check-out, Tasks]
  - CHECKIN_CHECKOUT_BOTTOM_NAV: [Today, Arrivals, Departures, Tasks]
  - CLEANER_BOTTOM_NAV: [Home, Cleaning, Tasks]
  - MAINTENANCE_BOTTOM_NAV: [Home, Maintenance, Tasks]
- File: `ihouse-ui/components/OMBottomNav.tsx`, lines 45-50: Manager mobile nav (PRIMARY_TABS)

**What was observed:** Each worker sub-role gets exactly the navigation tabs relevant to their job. The combined checkin_checkout role gets a 4-tab layout (unique among workers). Manager gets a separate OMBottomNav. Navigation is not filtered from a master list — each config is independently defined.

**Confidence:** HIGH

**Uncertainty:** None.

---

## Claim 6: Preview-as and Act-as are structurally distinct mechanisms

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/PreviewAsSelector.tsx` (228 lines): Preview mode with yellow banner "👀 PREVIEWING"
- File: `ihouse-ui/lib/PreviewContext.tsx` (123 lines): `isPreviewActive` flag, sessionStorage-based, X-Preview-Role header
- File: `ihouse-ui/components/ActAsSelector.tsx` (286 lines): Act-as mode with red banner "🔴 ACTING AS"
- File: `ihouse-ui/lib/ActAsContext.tsx` (408 lines): Scoped JWT with TTL, per-tab sessionStorage isolation

**What was observed:**
| Dimension | Preview-as | Act-as |
|-----------|-----------|--------|
| Token | SessionStorage simulation | Scoped JWT (real token) |
| Visual | Yellow "👀 PREVIEWING" | Red "🔴 ACTING AS" |
| Mutations | Blocked (isPreviewActive flag + X-Preview-Role header for server enforcement) | Allowed (full scoped token) |
| Tab | New tab | New tab |
| Session | User-controlled (Stop Preview button) | TTL-based countdown (default 3600s) |

**Confidence:** HIGH

**Uncertainty:** None. Both implementations are comprehensive and distinct.

---

## Claim 7: Dashboard (/dashboard) is shared across multiple roles

**Status:** DIRECTLY PROVEN

**Evidence basis:**
- File: `ihouse-ui/components/Sidebar.tsx`, lines 41-55: NAV_ITEMS shows `nav.dashboard → /dashboard` allowed for roles: admin, owner, worker, cleaner, checkin, maintenance
- File: `ihouse-ui/middleware.ts`: owner allowed prefix includes `/dashboard`; worker allowed prefix does NOT include `/dashboard`

**What was observed:** Sidebar lists dashboard as accessible to admin, owner, worker, cleaner, checkin, and maintenance. However, middleware for the `worker` role lists `/worker, /ops, /maintenance, /checkin, /checkout` — NOT `/dashboard`. This means workers and some sub-roles can see the dashboard nav link but middleware may block actual access. The `ops` role CAN access `/dashboard` per middleware.

This is a potential inconsistency: the Sidebar shows a nav item that middleware would block for certain roles.

**Confidence:** HIGH on the inconsistency observation. MEDIUM on the actual user impact (workers may use MobileStaffShell which doesn't render Sidebar at all).

**Uncertainty:** MobileStaffShell bypasses Sidebar entirely, so field workers never see the dashboard link. The inconsistency may be invisible in practice. But the `owner` role CAN access `/dashboard`, and whether the dashboard shows role-appropriate content for owners is unverified.

---

## Summary of Evidence

| Memo Claim | Evidence Status | Confidence |
|---|---|---|
| 7 distinct role surfaces | DIRECTLY PROVEN | HIGH |
| Three-shell architecture | DIRECTLY PROVEN | HIGH |
| Manager FULL_ACCESS | DIRECTLY PROVEN | HIGH |
| Owner visibility flags | PROVEN (flags), UNVERIFIED (query filtering) | HIGH / MEDIUM |
| Role-specific bottom nav | DIRECTLY PROVEN | HIGH |
| Preview/Act-as distinction | DIRECTLY PROVEN | HIGH |
| Dashboard shared across roles | PROVEN with inconsistency noted | HIGH |
