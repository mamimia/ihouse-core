# Phase 861 — Identity Merge & Auth Linking Closure

**Status:** Closed
**Prerequisite:** Phase 860 (Landing Page UI Fixes & Tab Responsive Scrolling)
**Date Closed:** 2026-03-23

## Goal

Resolve the dual admin identity problem (admin@domaniqo.com + esegeve@gmail.com), fix the Google identity linking flow end-to-end, and deliver a production-ready Linked Login Methods UI on both admin and public profile surfaces.

## Invariant (if applicable)

- Canonical admin identity: `25407914-2071-4ee8-b8ae-8aa5967d8f20` (admin@domaniqo.com) with both `email` and `google` providers linked.
- No duplicate auth users for the same human — identity unification is the canonical path.
- `linkIdentity` callback must preserve origin route (admin → admin, public → public).

## Design / Files

| File | Change |
|------|--------|
| `src/api/auth_router.py` | MODIFIED — GET /auth/profile now returns `providers` as `[{provider, email}]` objects + `auth_method` + `auth_email` |
| `ihouse-ui/lib/identityLinking.tsx` | MODIFIED — stores `ihouse_linking_return` (origin path) in sessionStorage before linkIdentity redirect |
| `ihouse-ui/app/(public)/auth/callback/page.tsx` | MODIFIED — reads stored return route, redirects there instead of hardcoded `/profile` |
| `ihouse-ui/app/(app)/admin/profile/page.tsx` | MODIFIED — ProviderInfo interface, "Currently logged in with: email" text, explicit "Unlink" button, provider pills with emails |
| `ihouse-ui/app/(public)/profile/page.tsx` | MODIFIED — Same UI improvements as admin profile |

## Database Changes

| Action | Detail |
|--------|--------|
| `UPDATE properties` | Migrated 2 rows (id=48, 59) from `736f4d6a` → `25407914` submitter_user_id |
| `DELETE tenant_permissions` | Removed duplicate row #37 for `736f4d6a` |
| `DELETE auth.identities` | Removed `736f4d6a` Google identity |
| `DELETE auth.sessions` | Removed `736f4d6a` sessions |
| `DELETE auth.refresh_tokens` | Removed `736f4d6a` refresh tokens |
| `DELETE auth.users` | Removed duplicate user `736f4d6a-4c75-470a-ae84-cad9581a1a44` |
| Manual link | User manually linked Google identity to canonical user `25407914` via product UI |

## Result

**Build passes (Next.js + Python syntax). Backend auto-deployed via Railway. Frontend deployed to Vercel staging.**

- Canonical admin identity: `25407914` with email + google providers
- Duplicate identity `736f4d6a` fully removed from all tables
- linkIdentity callback preserves origin route
- "Currently logged in with: admin@domaniqo.com" shown on profile
- Provider pills show actual emails: "📧 Email/Password — admin@domaniqo.com", "Google — esegeve@gmail.com"
- Explicit "Unlink" button replaces cryptic ✕
- User manually verified Google linking end-to-end on staging
