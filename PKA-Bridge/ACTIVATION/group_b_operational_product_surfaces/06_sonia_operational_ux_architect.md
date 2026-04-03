# Activation Memo: Sonia — Operational UX Architect

**Phase:** 972 (Group B Activation)
**Date:** 2026-04-03
**Grounded in:** Direct reading of ihouse-core repository (ihouse-ui/middleware.ts, roleRoute.ts, AdaptiveShell.tsx, MobileStaffShell.tsx, Sidebar.tsx, OMSidebar.tsx, BottomNav.tsx, OMBottomNav.tsx, owner_portal_v2_router.py, manager/page.tsx)

---

## 1. What in the Current Real System Belongs to This Domain

Sonia's domain is the structural differentiation between role surfaces. The real system implements this differentiation at four layers:

- **Routing layer**: `middleware.ts` ROLE_ALLOWED_PREFIXES map defines which URL prefixes each role can access. Deny-by-default — roles not listed get blocked at the edge.
- **Landing layer**: `roleRoute.ts` ROLE_ROUTES map determines where each role lands after login. Phase 948a adds worker sub-role resolution from JWT.
- **Shell layer**: `AdaptiveShell.tsx` detects role context and switches between three shell types: standard Sidebar (admin, owner, ops), OMSidebar (manager), MobileStaffShell (all field workers).
- **Navigation layer**: `Sidebar.tsx` NAV_ITEMS are role-filtered. `OMSidebar.tsx` has a dedicated OM_NAV. `BottomNav.tsx` has 5 role-specific bottom nav configs for mobile workers.

## 2. What Appears Built

- **7 distinct role surfaces** with clear structural boundaries:
  - **Admin** (`/admin/*`): 37+ subdirectories — governance, staff management, analytics, DLQ, sync, integrations, templates, settings. Full-access role.
  - **Manager** (`/manager/*`): 8 pages — dedicated operational manager cockpit with morning briefing, alert dashboard, event stream, team view. Uses OMSidebar, NOT admin Sidebar. Managers do NOT access `/admin/*`.
  - **Owner** (`/owner`): Single portal page with 8 visibility flags (bookings, financial_summary, occupancy_rates on by default; maintenance_reports, guest_details, task_details, worker_info, cleaning_photos off by default).
  - **Ops** (`/ops`): Hub dashboard for field supervision — today's arrivals, departures, active tasks.
  - **Worker sub-role surfaces** (`/ops/checkin`, `/ops/checkout`, `/ops/checkin-checkout`, `/ops/cleaner`, `/ops/maintenance`): Each is a task-focused surface scoped to that worker's daily job.
  - **Generic worker** (`/worker`): Role-aware landing that resolves sub-role from JWT and shows role-specific stats with CTA to the correct ops surface.
  - **Dashboard** (`/dashboard`): Role-agnostic home accessible to admin, owner, and ops.

- **MobileStaffShell**: All field worker surfaces bypass the standard sidebar and render in a forced dark-theme, full-screen mobile shell. Touch targets ≥44px. Safe area insets for notch and home indicator. Phone simulation (480px) on desktop for dev testing.

- **OMSidebar**: Manager gets a completely separate navigation structure — Hub, Alerts, Stream, Team as primary tabs. This is NOT a filtered version of the admin sidebar; it's a distinct component.

- **Role-specific bottom navigation**: 5 distinct BottomNav configs (CHECKIN_BOTTOM_NAV, CHECKOUT_BOTTOM_NAV, CHECKIN_CHECKOUT_BOTTOM_NAV, CLEANER_BOTTOM_NAV, MAINTENANCE_BOTTOM_NAV) plus OMBottomNav for manager mobile.

- **Preview-as and Act-as**: Two distinct mechanisms for admin to experience other roles. Preview uses sessionStorage + X-Preview-Role header (yellow banner). Act-as uses scoped JWT in new tab with TTL countdown (red banner).

- **Owner visibility flags**: 8 flags in `owner_portal_v2_router.py` with sensible defaults — show revenue/bookings/occupancy, hide costs/worker-info/cleaning-photos. Admin can toggle per owner per property.

## 3. What Appears Partial

- **Owner surface depth**: Only a single `/owner` page exists. The visibility flags and backend API (summary, bookings, occupancy) are built, but the frontend likely needs richer views — financial detail drill-down, property-specific views, booking history. The 8 visibility flags exist in the API but frontend filtering enforcement was not fully traced.
- **Ops hub** (`/ops/page.tsx`): Exists as a dashboard but its content depth (whether it shows real-time SLA status, worker locations, or just task counts) was not fully mapped.
- **Dashboard** (`/dashboard`): Shared across admin/owner/ops but whether it presents role-appropriate content (not just role-filtered access) is unclear. The same page serves governance (admin) and supervision (ops).

## 4. What Appears Missing

- **No dedicated guest surface routing**: Guest portal (`/guest/*`) is not in the ROLE_ALLOWED_PREFIXES map, suggesting it uses a separate auth path (token-based, not JWT role-based). This is architecturally correct but means guest experience is fully decoupled from the role-surface system.
- **No identity_only surface beyond welcome**: The `identity_only` role maps to `/welcome, /profile, /get-started, /my-properties` but these appear to be onboarding gates, not an operational surface. Users in `identity_only` have no functional product surface.
- **No role-switching without full re-auth**: A user who holds multiple roles (e.g., admin who is also an owner) must use Preview-as or Act-as rather than a native role-switch mechanism.

## 5. What Appears Risky

- **Dashboard serving multiple roles**: `/dashboard` is accessible to admin, owner, worker, cleaner, and ops (per Sidebar NAV_ITEMS). If it doesn't dynamically adapt content per role, lower-privilege roles may see admin-oriented data (DLQ status, sync health) or experience a sparse/confusing surface.
- **Manager isolation from admin**: Managers have FULL_ACCESS in middleware (same as admin) but land on `/manager`. This means middleware does NOT prevent a manager from manually navigating to `/admin/*` routes. The structural boundary is enforced by the OMSidebar (which doesn't link to admin pages), not by the middleware. If a manager discovers an admin URL, they can access it. This may be intentional (managers are trusted) or a gap.
- **Owner visibility flag enforcement at query level**: The flags exist and toggle endpoints work, but whether the summary query actually filters results based on these flags (rather than just returning everything) was not traced to the SQL/RPC level. If filtering is only frontend-side, it's a data leak.

## 6. What Appears Correct and Worth Preserving

- **Deny-by-default middleware**: Every role is explicitly listed in ROLE_ALLOWED_PREFIXES. Unlisted prefixes are blocked. This is the correct security posture.
- **Three-shell architecture**: Standard Sidebar, OMSidebar, MobileStaffShell. Each serves a structurally different use case. Not a single generic shell with role-based hiding — three genuinely different experiences.
- **Forced dark theme for field workers**: MobileStaffShell forces dark theme at the component level. Field workers in rental units (often checking in at night) get appropriate visual treatment without a theme toggle.
- **Worker sub-role routing from JWT**: Phase 948a resolves worker sub-role from JWT claims, routing cleaners to `/ops/cleaner`, maintenance to `/ops/maintenance`, etc. Workers never see a generic "pick your role" screen.
- **Preview-as / Act-as distinction**: Preview is read-only in same tab; Act-as is a scoped session in new tab. This correctly separates "I want to see what they see" from "I need to do something as them."
- **Owner default visibility**: Progressive trust model — show revenue/occupancy by default, hide cost details until admin enables them. This matches real property management trust dynamics.

## 7. What This Role Would Prioritize Next

1. **Audit the dashboard per-role experience**: Verify what each role actually sees on `/dashboard`. If it's the same page for admin and cleaner, this is a surface differentiation failure.
2. **Trace owner visibility flag enforcement**: Confirm that the summary query respects visibility flags at the SQL level, not just frontend rendering.
3. **Clarify manager-admin boundary**: Determine if FULL_ACCESS for managers is intentional (trust model) or if managers should be restricted to `/manager/*` prefixes only.
4. **Map the ops hub content**: Determine whether `/ops` shows supervisory data (SLA breaches, worker status, aggregate task progress) or just a task list.

## 8. Dependencies on Other Roles

- **Daniel**: Sonia needs Daniel to confirm whether FULL_ACCESS for managers is a deliberate permission decision or an oversight. This affects whether the manager surface is structurally isolated or just navigationally isolated.
- **Talia**: Sonia defines the structural boundaries; Talia defines the interaction patterns within them. The dashboard role-adaptation question requires Talia's input on what each role should experience.
- **Marco**: Marco validates that MobileStaffShell is functionally correct on real devices. Sonia defines that it should exist as a distinct shell; Marco confirms it works.
- **Miriam (Group C)**: The owner surface depth question directly feeds Miriam's owner experience strategy.

## 9. What the Owner Most Urgently Needs to Understand

The role-surface architecture is significantly more mature than a typical early-stage SaaS. The system has genuine structural differentiation — not just filtered menus — with three distinct shell types, role-specific bottom navigation, forced dark theme for field workers, and a dedicated manager cockpit separate from admin.

Two structural questions need attention:

1. **Manager FULL_ACCESS**: Managers can technically navigate to any admin page via URL. The surface isolation is navigational (OMSidebar doesn't link there) but not enforced at middleware level. If this is intentional, document it. If not, restrict manager prefixes in middleware.

2. **Owner visibility enforcement depth**: The 8 visibility flags are architecturally sound, but until query-level filtering is confirmed, there's a potential data transparency leak where owners see more than their admin intended.

The system correctly treats each role as a distinct operational product. This is a strong architectural foundation that most property management platforms never achieve.
