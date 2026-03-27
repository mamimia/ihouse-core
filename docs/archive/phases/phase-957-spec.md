# Phase 957 — Global Theme Consistency

**Status:** Closed
**Prerequisite:** Phase 956 (Stat Box Visual Alignment)
**Date Closed:** 2026-03-27

## Goal

Eliminate mixed-theme behavior across the admin product where some pages loaded in dark mode and others in light mode. Establish a single, globally consistent theme system where: default is Light, toggle switches entire product to Dark, and no page independently overrides the global theme.

## Root Cause

Three separate mechanisms were fighting each other:

1. **`app/(app)/admin/layout.tsx`** — `useEffect` that forced `data-theme="light"` on mount and removed the attribute on unmount. This made admin pages (Properties, Owners, Staff, Admin) always light.
2. **`components/ForceLight.tsx`** — Same pattern, used by specific sub-pages. On cleanup, it restored to localStorage value (which defaulted to dark if OS preference was dark).
3. **`styles/tokens.css`** — `@media (prefers-color-scheme: dark)` CSS block that hijacked all CSS variables when `data-theme` attribute was absent (`:root:not([data-theme="light"])`). This made non-admin pages dark for users with OS dark mode.

The combination meant: admin pages = forced light, non-admin pages = OS-dependent (usually dark), and the user's toggle choice was ignored by both overrides.

## Design / Files

| File | Change |
|------|--------|
| `ihouse-ui/app/(app)/admin/layout.tsx` | MODIFIED — Removed `useEffect` that forced `data-theme="light"`. Theme now governed exclusively by ThemeProvider. |
| `ihouse-ui/components/ForceLight.tsx` | MODIFIED — Disabled all DOM attribute manipulation. Component now returns null immediately. |
| `ihouse-ui/styles/tokens.css` | MODIFIED — Removed entire `@media (prefers-color-scheme: dark)` block. Dark mode now activated ONLY via explicit `[data-theme="dark"]` attribute. |
| `ihouse-ui/components/ThemeProvider.tsx` | MODIFIED — `getSystemPreference()` now always returns `'light'`, ignoring OS `prefers-color-scheme`. Default theme is unconditionally Light. |

## Invariants Locked

- Default theme is Light globally — no page, layout, or OS preference can override this.
- Dark mode is activated ONLY when user explicitly toggles (sets `data-theme="dark"` via ThemeProvider).
- No component may independently set `data-theme` on `document.documentElement`.
- Theme is stored in `localStorage('domaniqo-theme')` and persisted across sessions.
- The anti-flicker inline script in `layout.tsx` reads localStorage on first paint (no FOUC).

## Result

- All admin pages (Dashboard, Tasks, Bookings, Calendar, Financial, Manager, Guests, Owners, Properties, Manage Staff, Admin, More) render consistently in the same theme.
- Default experience is Light for all users.
- Toggle correctly switches the entire product to Dark.
- Deployed to Vercel staging.
