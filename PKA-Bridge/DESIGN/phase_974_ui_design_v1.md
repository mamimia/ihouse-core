# Phase 974 — UI Design V1: Product Surface Architecture

**Date:** 2026-04-03
**Depends on:** Phase 973 (Group C Activation — full system understanding)
**Status:** In Progress

---

## Objective

Build Version 1 of the full product UI surface architecture for Domaniqo / iHouse Core. Mobile-first, one coherent design system across all roles. Not final UI — this is the structural foundation.

## Working Order

1. **OPS Manager** (style anchor) — ✅ COMPLETE
2. Field-worker family (Check-In, Check-Out, Cleaner, Maintenance) — NEXT
3. Stakeholder-facing (Admin, Owner, Guest) — PENDING
4. Public, Submitter — PENDING

## Source Material Used

### Real System (ihouse-core)
- All manager frontend pages (`/app/(app)/manager/`)
- OMSidebar, OMBottomNav, AdaptiveShell components
- Middleware ROLE_ALLOWED_PREFIXES and FULL_ACCESS_ROLES
- BottomNav role-specific configurations

### Design Direction (Team_Inbox)
- Ops Manager Interactive Prototype v3 (25 screens)
- Check In Check Out prototypes (3 versions)
- Cleaner Operational UI Direction
- Maintenance Operational UI Direction
- SCREENS_PREVIEW (7 role home screens)

### Product Brief (User-Provided)
- Current Stay Portal v1/v2 — Guest portal vision document with 7-block structure, hospitality-first design direction, My Pocket concept

## Artifacts Created

### Shared Foundation
- `UI_DESIGN_V1/00_DESIGN_SYSTEM.md` — Full design system: typography, colors, urgency system, components, navigation, responsive strategy, role personality

### OPS Manager (Complete)
- `UI_DESIGN_V1/OPS_MANAGER/01_screen_map.md` — 27 screens mapped across 7 sections
- `UI_DESIGN_V1/OPS_MANAGER/02_navigation_and_links.md` — Full navigation flow diagram, link table, drawer/push/modal decision rules, deep-link patterns
- `UI_DESIGN_V1/OPS_MANAGER/03_screen_definitions.md` — Detailed layout structures (mobile + desktop) for key screens, component reference
- `UI_DESIGN_V1/OPS_MANAGER/04_profile_structure.md` — Profile sections, mode indicators
- `UI_DESIGN_V1/OPS_MANAGER/05_states_and_edge_cases.md` — Per-screen states, edge cases, animation inventory
- `UI_DESIGN_V1/OPS_MANAGER/06_open_questions.md` — 5 design questions, 4 technical questions, 4 known gaps

## Design Decisions Made

1. **Mobile-first, not mobile-only**: Desktop is responsive expansion, not separate product
2. **One design system**: Shared typography (Manrope + Inter), shared urgency system (4 states), shared component patterns (left-accent cards, KPI strips, bottom nav)
3. **Role personality within system**: Each role has visual cues (color accents, specific components) but stays within the same design language
4. **Command center aesthetic for manager**: Dark backgrounds, KPI strips, stream cards — distinct from worker dark theme (which is operational, not strategic)
5. **Drawer/Push/Modal pattern**: Clear rules for when to use each navigation pattern

## Next Steps

1. Design CHECK_IN_STAFF and CHECK_OUT_STAFF (can share significant structure)
2. Design CLEANER (spatial/room-based, not sequential)
3. Design MAINTENANCE (priority-driven, access-code-prominent)
4. Incorporate Guest Portal v1/v2 brief into GUEST UI design
